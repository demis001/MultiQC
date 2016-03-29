#!/usr/bin/env python

""" MultiQC module to parse output from methylQA """

from __future__ import print_function
from collections import OrderedDict
import logging
import os
import re

from multiqc import config, BaseMultiqcModule

# Initialise the logger
log = logging.getLogger(__name__)

class MultiqcModule(BaseMultiqcModule):

    def __init__(self):

        # Initialise the parent object
        super(MultiqcModule, self).__init__(name='methylQA', anchor='methylqa', 
        target='methylQA', href="http://methylqa.sourceforge.net/", 
        info=" - a methylation sequencing data quality assessment tool.")

        # Find and load any methylQA reports
        self.methylqa_data = dict()
        self.methylqa_coverage_counts = dict()
        self.methylqa_coverage_percentages = dict()
        for f in self.find_log_files(config.sp['methylQA']):
            self.parse_methylqa_logs(f)

        if len(self.methylqa_data) == 0:
            log.debug("Could not find any reports in {}".format(config.analysis_dir))
            raise UserWarning

        log.info("Found {} reports".format(len(self.methylqa_data)))
        
        # Write parsed report data to a file
        self.write_data_file(self.methylqa_data, 'multiqc_methylQA')
        
        # Basic Stats Table
        self.methylqa_general_stats_table()
        
        # Alignment bar plot - only one section, so add to the module intro
        self.intro += self.methylqa_alignment_plot()


    def parse_methylqa_logs(self, f):
        
        # Get s_name from first input file if possible
        s_name = f['s_name']
        if f['f'][0].startswith('files provided'):
            s_name = os.path.basename(f['f'][0])
        
        parsed_data = {}
        regexes = {
            'mappable_reads': r"uniquely mappable reads \(pair\): (\d+)",
            'quality_failed': r"quality failed mapped reads \(pair\) in the bismark bam: (\d+)",
            'oversized_reads': r"oversized mapped reads \(pair\) in the bismark bam: (\d+)",
            'mapped_bases': r"total base of uniquely mapped reads \(pair\): (\d+)",
            'coverage': r"total base of uniquely mapped reads \(pair\) cover genome base \(\d+\): ([\d\.]+)X",
            'CHG_count_meth': r"number of methylated C in CHG context \(was protected\): (\d+)",
            'CHG_count_unmeth': r"number of not methylated C in CHG context \(was converted\): (\d+)",
            'CHG_percent_meth': r"C->T convertion rate in CHG context: ([\d\.]+)%",
            'CHH_count_meth': r"number of methylated C in CHH context \(was protected\): (\d+)",
            'CHH_count_unmeth': r"number of not methylated C in CHH context \(was converted\): (\d+)",
            'CHH_percent_meth': r"C->T convertion rate in CHH context: ([\d\.]+)%",
            'CG_count_meth': r"number of methylated C in CpG context \(was protected\): (\d+)",
            'CG_count_unmeth': r"number of not methylated C in CpG context \(was converted\): (\d+)",
            'CG_percent_meth': r"C->T convertion rate in CpG context: ([\d\.]+)%",
            'CN_count_meth': r"number of methylated C in Unknown context \(was protected\): (\d+)",
            'CN_count_unmeth': r"number of not methylated C in Unknown context \(was converted\): (\d+)",
            'CN_percent_meth': r"C->T convertion rate in Unknown context: 1([\d\.]+)%",
        }
        for k, r in regexes.items():
            match = re.search(r, f['f'])
            if match:
                parsed_data[k] = float(match.group(1))
        
        # Parse the coverage histogram
        hist = False
        for l in f['f'].split(os.linesep):
            if hist is not False:
                try:
                    s = l.split()
                    hist['counts'][s[0]] = int(s[1])
                    hist['percentages'][s[0]] = float(s[2])
                except IndexError:
                    break
            if 'Times covered           Count    Percent  |' in l:
                hist = { 'counts': OrderedDict(), 'percentages': OrderedDict() }
        if hist is not False and len(hist) > 0:
            self.methylqa_coverage_counts[s_name] = hist['counts']
            self.methylqa_coverage_percentages[s_name] = hist['percentages']
        
        if len(parsed_data) > 0:
            if s_name in self.methylqa_data:
                log.debug("Duplicate sample name found! Overwriting: {}".format(s_name))
            self.add_data_source(f, s_name)
            self.methylqa_data[s_name] = parsed_data


    def methylqa_general_stats_table(self):
        """ Take the parsed stats from the methylQA report and add it to the
        basic stats table at the top of the report """
        
        headers = OrderedDict()
        headers['coverage'] = {
            'title': 'Fold Coverage',
            'min': 0,
            'scale': 'YlGn',
            'format': '{:.1f}X'
        }
        self.general_stats_addcols(self.methylqa_data, headers)

    def methylqa_alignment_plot (self):
        """ Make the HighCharts HTML to plot the alignment rates """
        
        pconfig = {
            'id': 'methylqa_coverage',
            'title': 'CpG Coverage',
            'categories': True,
            'ylab': 'CpG Counts',
            'xlab': 'Times covered',
            'ymin': 0,
            'data_labels': [
                {'name': 'Counts', 'ylab': 'CpG Counts' },
                {'name': 'Percentages', 'ylab': '% CpGs', 'ymax': 100 }
            ]
        }    
        return self.plot_xy_data([self.methylqa_coverage_counts, self.methylqa_coverage_percentages], pconfig)