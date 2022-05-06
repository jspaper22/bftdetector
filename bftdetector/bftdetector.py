from .testinput_generator import TestInputGenerator
from .tpmanager import TPManager
from .domdiff import DomDiff
from .jscfg.jscfgmanager import JSCFGManager
from . import calltrace
from .success_checker import SuccessChecker
from .bftdetector_option import BFTDetectorOption, PromotionalMethod

import subprocess
from threading import Timer
import psutil
import time
import os, glob
import pickle
from copy import deepcopy
from pathlib import Path
import platform

MODULE_PATH = str(Path(__file__).resolve().parent)

PUPPET_RUN_PATH = MODULE_PATH + '/js/puppet/run_puppet.js'
EXCLUDE_JS_LIST_PATH = MODULE_PATH + '/exclude_list.cfg'
CHROME_PATH = MODULE_PATH + '/chromium/chrome'
if platform.system() == 'Darwin':
    CHROME_PATH = MODULE_PATH + '/chromium_mac/Chromium.app/Contents/MacOS/Chromium'

V8MOD_MODE = ['disabled', 'ctrace', 'stmt_trace', 'cfmod', 'js_ctrace', 'full_ctrace', 'stat_only']
CALL_TRACE_MODE = 'full_ctrace'
STACK_SIZE = 20000

tigen = TestInputGenerator()


class BFTDetector:
    def __init__(self, options: BFTDetectorOption, promotional_method: PromotionalMethod):
        options = deepcopy(options)
        options.working_dir = os.path.abspath(options.working_dir) + '/'
        self.options = options
        self.adblock = promotional_method == PromotionalMethod.ANTI_ADBLOCKER
        self.test_js = ''
        self.jscfgs = {}
        self.excluded_js_list = None
        self.success_checker = None
        self.terminate_cfmod = False
        self.terminate_browser_timeout = options.timeout + 20
        self.sidtable = {}

    def clear_chrome_cache(self, inst_id=None):
        if inst_id:
            os.system('rm -rf ' + self.get_instance_path(inst_id) + 'chrome_dir')
        else:
            for i in range(self.options.multiprocess_cnt):
                os.system('rm -rf ' + self.get_instance_path(str(i + 1)) + 'chrome_dir')

    def clean_tmp(self):
        os.system('rm -rf ' + self.get_test_path() + 'tmpdir')

    def launch_puppet(self, mode, timeout_sec=None, kill_if_event=False, inst_id=None):
        def kill_puppet(proc):
            process = psutil.Process(proc.pid)
            for proc2 in process.children(recursive=True):
                proc2.kill()
            process.kill()

        def comm_realtime(proc):
            while True:
                line = proc.stdout.readline().rstrip()
                if not line:
                    break
                yield line

        cmd = ['node', PUPPET_RUN_PATH, CHROME_PATH, self.get_test_path(), mode]
        if inst_id:
            cmd.append(inst_id)
        # print(' '.join(cmd))

        run = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = ''
        err = ''
        timer = None

        if timeout_sec is not None:
            timer = Timer(timeout_sec, kill_puppet, [run])
            timer.start()

        try:
            if kill_if_event:
                for out in comm_realtime(run):
                    # print out
                    output += out + '\n'
                    if 'EVENT HAPPENED' in out:
                        # print '>> Event Happened :Terminate browser'
                        time.sleep(1)
                        kill_puppet(run)
                        break
            else:
                output, err = run.communicate()
                output = output.decode('utf-8')
                err = err.decode('utf-8')
                # if run.returncode != 0:
                #     exit(err)

        finally:
            if timer is not None:
                timer.cancel()

        return output, err

    def create_config_file(self, mode, data=None, url='', arg='', inst_id=None, stat_mode=False):
        if data is None:
            data = []
        output = 'test_name=' + self.options.test_name + '\n'
        output += 'v8mod_mode=' + str(V8MOD_MODE.index(mode)) + '\n'
        output += 'stat=' + ('1' if stat_mode else '0') + '\n'
        output += 'exclude_list=' + EXCLUDE_JS_LIST_PATH + '\n'
        output += 'url=' + url + '\n'
        output += 'stack_size=' + str(STACK_SIZE) + '\n'
        output += 'arg=' + str(arg) + '\n\n'

        if mode == 'stmt_trace':
            for sid in data:
                source_url = self.get_sourceurl_from_sid(sid)
                if source_url == '':
                    continue
                fid_output = []
                for fid in data[sid]:
                    fid_output.append(fid + ':' + ','.join(data[sid][fid]))

                output += source_url + '\n' + sid + '\n' + '|'.join(fid_output) + '\n\n'
        elif mode == 'cfmod':
            for sid in data:
                source_url = self.get_sourceurl_from_sid(sid)
                if source_url == '':
                    continue
                output += source_url + '\n' + sid + '\n' + ','.join(data[sid]) + '\n\n'
        elif mode == 'ctrace':
            for source_url in data:
                output += source_url + '\n' + 'n/a' + '\n'
                # sort the list
                sorted_list = [int(x) for x in data[source_url]]
                sorted_list.sort()
                sorted_list = [str(x) for x in sorted_list]
                output += ','.join(sorted_list) + '\n\n'

        elif mode == 'js_ctrace':
            for source_url in data:
                output += source_url + '\n' + 'n/a' + '\n\n'

        path = self.get_test_path() + 'tmpdir/'
        if inst_id:
            path = self.get_instance_path(inst_id)
        with open(path + 'v8mod.cfg', 'w') as f:
            f.write(output)

    def get_test_path(self):
        return self.options.working_dir + self.options.test_name + '/'

    def get_instance_path(self, inst_id):
        return self.get_test_path() + 'tmpdir/inst' + inst_id + '/'

    def make_test_dir(self):
        testpath = self.get_test_path()
        # os.system('mkdir -p ' + testpath)
        os.system('mkdir -p ' + testpath + 'trace_a')
        os.system('mkdir -p ' + testpath + 'trace_b')
        os.system('mkdir -p ' + testpath + 'test_out/screenshot')
        os.system('mkdir -p ' + testpath + 'test_out/html')
        os.system('mkdir -p ' + testpath + 'tmpdir/tempjs')

        for i in range(self.options.multiprocess_cnt):
            os.system('mkdir -p ' + testpath + 'tmpdir/inst' + str(i + 1))

    def run_init(self, pages, inst_id):
        tigen.make_init_script(pages, self.options, inst_id)
        self.create_config_file('disabled', inst_id=inst_id)

        timeout = (self.options.timeout - 5) * len(pages) + 5
        self.launch_puppet('disabled', timeout_sec=timeout, inst_id=inst_id)

    def run_get_html(self, url, trace_side, inst_id=None, adblock=False):
        filepath = self.get_test_path() + 'trace_' + trace_side + '/' + str(int(time.time() * 1000))

        tigen.make_simple_visit(url, self.options, inst_id=inst_id, save_srcs=filepath, adblock=adblock,
                                trace_side=trace_side)
        self.create_config_file('disabled', inst_id=inst_id)
        self.launch_puppet('disabled', timeout_sec=self.terminate_browser_timeout, inst_id=inst_id)

    def run_get_calltrace(self, url, trace_side, inst_id=None, adblock=None):
        trace_mode = CALL_TRACE_MODE

        opt = deepcopy(self.options)
        opt.timeout = self.options.timeout_callstack_collection

        ctrace_id = str(int(time.time() * 100))

        self.test_js = tigen.make_simple_visit(url, opt, inst_id=inst_id, ctrace_mode=True,
                                               adblock=adblock, trace_side=trace_side)
        self.create_config_file(trace_mode, url=url, arg=ctrace_id, inst_id=inst_id)
        output, err = self.launch_puppet(trace_mode, inst_id=inst_id)

        pos = output.find('=====[Call Trace Saved]===== <')
        if pos == -1:
            exit('Getting call trace error\n' + output)
            return

        ctrace_path = self.get_test_path() + 'tmpdir/'
        if inst_id:
            ctrace_path = self.get_instance_path(inst_id)

        time.sleep(5)
        cmd = 'mv ' + ctrace_path + '*' + ctrace_id + '* ' + self.get_test_path() \
              + 'trace_' + trace_side + '/.' + ' >/dev/null 2>&1'
        os.system(cmd)

    def get_dom_diff(self):
        files1 = [f for f in glob.glob(self.get_test_path() + 'trace_a/*.html')]
        files2 = [f for f in glob.glob(self.get_test_path() + 'trace_b/*.html')]

        if len(files1) == 0 or len(files2) == 0:
            print('No trace files')
            return []

        ddf = DomDiff()
        diffs_a, diffs_b = ddf.getDomDiff(files1, files2, div_only=True)
        selectors_a = ddf.getSelectors(diffs_a)
        selectors_b = ddf.getSelectors(diffs_b)

        # remove redundancy
        red = selectors_a & selectors_b
        selectors_a -= red
        selectors_b -= red

        return [list(selectors_a), list(selectors_b)]

    def get_dom_diff2(self, div_only=True):
        files1 = [f for f in glob.glob(self.get_test_path() + 'trace_a/*.html')]
        files2 = [f for f in glob.glob(self.get_test_path() + 'trace_b/*.html')]

        if len(files1) == 0 or len(files2) == 0:
            print('No trace files')
            return []

        ddf = DomDiff()
        selectors_a, selectors_b, comm = ddf.getSelectorDiffwithCommon(files1, files2, div_only=div_only)

        return [list(selectors_a), list(selectors_b)]

    def is_exclude_js(self, url):
        if self.excluded_js_list is None:
            self.excluded_js_list = []
            with open(EXCLUDE_JS_LIST_PATH, 'r') as f:
                self.excluded_js_list = f.read().split('\n')

        for ex_js_str in self.excluded_js_list:
            if ex_js_str in url:
                return True

        return False

    def construct_urlsid_data(self):
        urlsid = {}
        with open(self.get_test_path() + 'tmpdir/tempjs/scripts.log', 'r') as f:
            js_list = f.read().split('\n')
            for js in js_list:
                if js == '':
                    continue
                sid, url = js.split('\t')
                urlsid[url] = sid

        return urlsid

    def get_js_list_to_trace(self):
        excluded_js_list = []
        with open(EXCLUDE_JS_LIST_PATH, 'r') as f:
            excluded_js_list = f.read().split('\n')

        js_list = []
        with open(self.get_test_path() + 'tmpdir/tempjs/scripts.log', 'r') as f:
            js_list = f.read().split('\n')

            final_js_list = []
            for js in js_list:
                if js == '':
                    continue
                source_url = js.split('\t')[1]
                found = False
                for exjs in excluded_js_list:
                    if exjs in source_url:
                        found = True
                        break

                if not found:
                    final_js_list.append(js.split(','))

            js_list = final_js_list

        return js_list

    def get_ctrace_diff3(self, draw_ctrace=False):
        div_ct_callers, div_ct1, div_ct2, func_only_ct2 = calltrace.get_diff_calls(self.get_test_path())
        if draw_ctrace:
            calltrace.draw_diff(div_ct_callers, div_ct1, div_ct2)

        with open(self.get_test_path() + 'ctrace_diff.pkl', 'wb') as f:
            pickle.dump([list(div_ct1), list(div_ct2)], f)

        with open(self.get_test_path() + 'ctrace_func_only.pkl', 'wb') as f:
            pickle.dump(list(func_only_ct2), f)

        # delete ctrace files
        os.system('rm -rf ' + self.get_test_path() + 'trace_a/*ctrace* ' + self.get_test_path() + 'trace_a/jshash* ')
        os.system('rm -rf ' + self.get_test_path() + 'trace_b/*ctrace* ' + self.get_test_path() + 'trace_b/jshash* ')

        return list(div_ct1), list(div_ct2)

    def load_ctrace_diff_out(self):
        with open(self.get_test_path() + 'ctrace_diff.pkl', 'rb') as f:
            data = pickle.load(f)
        return data[0], data[1]

    def load_ctrace_func_only(self):
        with open(self.get_test_path() + 'ctrace_func_only.pkl', 'rb') as f:
            data = pickle.load(f)
        return data

    def get_jscfg(self, sid):
        # create cfg
        if sid in self.jscfgs:
            jscfg = self.jscfgs[sid]
        else:
            filepath = self.get_test_path() + 'tmpdir/tempjs/' + sid + '.js'
            if not os.path.isfile(filepath):
                return None
            jscfg = JSCFGManager()
            try:
                jscfg.build_cfgs(filename=filepath, script_id=sid)
            except:
                # print('CFG Build ERROR', filepath)
                return None

            self.jscfgs[sid] = jscfg

        return jscfg

    def analyze_ctrace_diff_out(self, ct_a, ct_b, draw_cfg=True, get_bb_trace=True):
        # combine call traces
        def combine_ct(ct, side, _combined_ct):
            for call_trace in ct:
                _caller = ':'.join(map(str, call_trace[2:4]))
                if _caller not in _combined_ct:
                    _combined_ct[_caller] = {'a': [], 'b': []}

                _combined_ct[_caller][side].append(
                    ':'.join(map(str, [call_trace[4], call_trace[0], call_trace[1], call_trace[5]])))

            return _combined_ct

        combined_ct = {}
        combined_ct = combine_ct(ct_a, 'a', combined_ct)
        combined_ct = combine_ct(ct_b, 'b', combined_ct)

        self.jscfgs = {}
        analyzed_data = {}
        for func_id in combined_ct:
            tmp = func_id.split(':')
            caller = {'sid': tmp[0], 'pos': tmp[1]}

            if caller['sid'] == '0':  # failed sid case
                continue
            if self.is_exclude_js(self.get_sourceurl_from_sid(caller['sid'])):
                continue

            jscfg = self.get_jscfg(caller['sid'])
            if jscfg is None:
                # print(caller['sid'], 'is not available')
                continue

            # get cfg of this function
            cfg_indx, cfg = jscfg.find_cfg(caller['pos'])
            if cfg_indx == -1:
                print('No function available at ', caller['sid'] + ':' + caller['pos'])
                continue
            # jscfg.draw_cfg(cfg_indx)
            # if caller['sid'] == '1908812446':
            #     jscfg.draw_cfg(cfg_indx)
            #     exit()

            data = {'caller': caller,
                    'ct_a': combined_ct[func_id]['a'],
                    'ct_b': combined_ct[func_id]['b'],
                    'call_pos_a': set([x.split(':')[0] for x in combined_ct[func_id]['a']]),
                    'call_pos_b': set([x.split(':')[0] for x in combined_ct[func_id]['b']]),
                    'bb_trace_offsets': [],
                    'tp_proposals': []}

            # if there are function pointers
            data['func_pointers'] = list(data['call_pos_a'] & data['call_pos_b'])

            # create tampering proposals
            data['tp_proposals'] = self.generate_tampering_proposals(data)
            analyzed_data[func_id] = data

            # For bb-level trace
            if get_bb_trace:
                # check if this func has no branch
                if len(cfg.basic_blocks) == 2:
                    continue

                # make BB trace data
                trace_offsets = set()
                bb_ids = set()
                call_bb_ids = set()
                for call_pos in data['call_pos_b']:
                    bb_list, offsets, call_bb = jscfg.get_bbs_to_track_all(cfg_indx, call_pos)
                    if offsets is None:  # less than 2 cds
                        continue

                    trace_offsets |= set(offsets)
                    bb_ids |= set([bb.id for bb in bb_list])
                    call_bb_ids.add(call_bb.id)

                data['bb_trace_offsets'] = list(trace_offsets)

                if draw_cfg:
                    jscfg.draw_with_cd(cfg_indx, list(call_bb_ids), list(bb_ids), True,
                                       output_path=self.get_test_path())
                    os.system('rm ' + self.get_test_path() + '*.gv')

        # save analyzed data
        with open(self.get_test_path() + 'analyzed_ctrace_diff.pkl', 'wb') as f:
            pickle.dump(analyzed_data, f)

        # import pprint
        # pprint.pprint(analyzed_data)

        tp_offsets_all = self.generate_tp_offsets(analyzed_data, 'all')
        if len(tp_offsets_all) == 0:
            print('No test inputs generated. Terminating the test.')
            exit()

        test_inputs = []
        for sid in tp_offsets_all:
            for tp in tp_offsets_all[sid]:
                test_inputs.append({sid: [tp]})

        with open(self.get_test_path() + 'test_inputs.pkl', 'wb') as f:
            pickle.dump(test_inputs, f)

        return test_inputs

    def load_test_inputs(self):
        with open(self.get_test_path() + 'test_inputs.pkl', 'rb') as f:
            return pickle.load(f)

    def generate_tampering_proposals(self, data):
        caller_sid = data['caller']['sid']
        jscfg = self.get_jscfg(caller_sid)
        tps = TPManager.generate_tp(jscfg, data)

        return tps

    def generate_tp_offsets(self, analyzed_data, tp_type):
        tp_offsets = {}
        for key, item in analyzed_data.items():
            if len(item['tp_proposals'][tp_type]) == 0:
                continue
            sid = item['caller']['sid']
            if sid not in tp_offsets:
                tp_offsets[sid] = set()

            tp_offsets[sid] |= set(item['tp_proposals'][tp_type])

        for sid in tp_offsets:
            tp_offsets[sid] = list(tp_offsets[sid])
            tp_offsets[sid].sort()

        return tp_offsets

    def load_analyzed_ctrace_diff_data(self):
        with open(self.get_test_path() + 'analyzed_ctrace_diff.pkl', 'rb') as f:
            return pickle.load(f)

    def run_clean(self, url, inst_id=None, save_result_id=None, adblock=None, no_close=None, trace_side=None):
        self.create_config_file('disabled', inst_id=inst_id)
        self.test_js = tigen.make_simple_visit(url, self.options, inst_id=inst_id, save_result=save_result_id,
                                               adblock=adblock, no_close=no_close, trace_side=trace_side)
        self.launch_puppet('disabled', inst_id=inst_id)

    def run_cfmod(self, url, offsets, inst_id=None, save_result_id=None, adblock=None):
        # if inst_id is not None:
        #     self.clear_chrome_cache(inst_id=inst_id)
        indx = save_result_id
        if save_result_id is not None and type(save_result_id) == int:
            save_result_id = str(save_result_id).zfill(3)

        tigen.make_simple_visit(url, self.options, inst_id=inst_id, save_result=save_result_id, adblock=adblock,
                                trace_side='b')
        self.create_config_file('cfmod', offsets, inst_id=inst_id)

        timeout_sec = self.options.timeout + 20

        output, err = self.launch_puppet('cfmod', timeout_sec=timeout_sec, inst_id=inst_id)
        if save_result_id is not None and self.success_checker is not None:
            ret = self.success_checker.check_success(save_result_id)
            self.print_test_result(indx, offsets, ret)

            #print(indx, offsets, ret)
            if self.options.exit_when_succeed and ret == 'Success':
                self.terminate_cfmod = True

        else:
            pass
            # print()
        return ''

    def run_confirm_test(self, url, offsets, inst_id=None, adblock=None):
        tigen.make_simple_visit(url, self.options, inst_id=inst_id, adblock=adblock,
                                trace_side='b', no_close=True)
        self.create_config_file('cfmod', offsets, inst_id=inst_id)
        self.launch_puppet('cfmod', inst_id=inst_id)

    def duplicate_session(self):
        for i in range(1, self.options.multiprocess_cnt):
            indx = str(i + 1)
            os.system('rm -rf ' + self.get_instance_path(indx) + 'chrome_dir')
            os.system(
                'cp -R ' + self.get_instance_path('1') + 'chrome_dir ' + self.get_instance_path(indx) + 'chrome_dir')

    def run_clean_visits(self, urls, inst_id=None):
        self.create_config_file('disabled', inst_id=inst_id)
        self.test_js = tigen.make_simple_visit(urls, self.options, inst_id=inst_id)
        timeout = (self.options.timeout - 5) * len(urls) + 5
        self.launch_puppet('disabled', inst_id=inst_id, timeout_sec=timeout)

    def init_success_checker(self):
        self.success_checker = SuccessChecker(self.get_test_path())

    def run_stat(self, url, stat_mode='stat_only', adblock=None):
        # stat_list = []
        stat_sum = [0, 0, 0, 0]
        for i in range(10):
            _trace_mode = CALL_TRACE_MODE
            if stat_mode == 'stat_only':
                _trace_mode = 'stat_only'
                self.test_js = tigen.make_simple_visit(url, self.options, adblock=adblock, stat_mode=True)
                self.create_config_file('stat_only', url=url, stat_mode=True)
            elif stat_mode == 'ctrace':
                opt = deepcopy(self.options)
                opt.stop_loading_timer = 120
                opt.timeout_callstack_collection = 120
                ctrace_id = str(int(time.time() * 100))
                self.test_js = tigen.make_simple_visit(url, opt, adblock=adblock, stat_mode=True)
                self.create_config_file(_trace_mode, [], url=url, arg=ctrace_id, stat_mode=True)

            output, err = self.launch_puppet(_trace_mode)
            # print(output)
            pos = output.find('>>RUNTIME:')
            if pos == -1:
                print('Getting stat error\n' + output)
                return

            pos2 = output.find('\n', pos)
            stats = output[pos + 10:pos2].split(',')
            stat_sum = [stat_sum[i] + float(stats[i]) for i in range(4)]

        stat_avg = [str(x / 10) for x in stat_sum]
        print('\t'.join(stat_avg), end='\t')

    def get_sourceurl_from_sid(self, sid):
        if sid in self.sidtable:
            return self.sidtable[sid]

        jshash = self.get_test_path() + 'tmpdir/tempjs/scripts.log'
        with open(jshash, 'r') as f:
            lines = f.read().split('\n')
            for line in lines:
                items = line.split('\t')
                if items[0] == sid:
                    self.sidtable[sid] = items[1]
                    return items[1]

        print('JS hash not found: ', sid)
        return ''

    def get_pos_from_offset(self, sid, offset):
        filepath = self.get_test_path() + 'tmpdir/tempjs/' + sid + '.js'
        with open(filepath, 'r') as f:
            return offset_to_pos(f.read(), offset)

    def print_test_result(self, indx, offsets, ret):
        output = '> Test ID: %3d %11s\n' % (indx, '[ ' + ret + ' ]')
        for sid in offsets:
            filepath = self.get_test_path() + 'tmpdir/tempjs/' + sid + '.js'
            jsdata = ''
            with open(filepath, 'r') as f:
                jsdata = f.readlines()

            output += '  + JS Source URL: %s \n' % self.get_sourceurl_from_sid(sid)
            for offset in offsets[sid]:
                inputs = offset.split(',')
                for input in inputs:
                    items = input.split(':')
                    line, column = offset_to_pos(jsdata, int(items[0]))
                    if items[2] == '2':
                        action = '    - Forced execution to branch #' + items[1]
                    else:
                        action = '    - Skip func. call or the branch #' + items[1]

                    output += action + ' at (%d:%d)\n' % (line, column)

        print(output)

#
# def pos_to_offset(data, line, column):
#     line -= 1
#     column -= 1
#     offset = 0
#
#     for i in range(len(data)):
#         if i == line:
#             offset += column
#             break
#
#         offset += len(data[i])
#
#     return offset

def offset_to_pos(data, offset):
    # to handle the last offset
    data[-1] += ' '

    cur_offset = 0
    line = 0
    column = 0
    for i in range(len(data)):
        line_len = len(data[i])
        if cur_offset + line_len > offset:
            line = i + 1
            column = offset - cur_offset + 1
            break

        cur_offset += line_len

    return line, column
