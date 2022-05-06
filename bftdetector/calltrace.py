import glob
import os, platform
from pathlib import Path

MODULE_PATH = str(Path(__file__).resolve().parent)


def load_traces(side, test_path):
    trace_path = test_path + 'trace_' + side + '/'

    files = [os.path.basename(f) for f in glob.glob(trace_path + 'ctrace_*')]

    ctloader_path = MODULE_PATH + '/cpp/ctloader_mp'
    if platform.system() == 'Darwin':
        ctloader_path += '_mac'

    cmd = [ctloader_path, trace_path] + files
    # print(' '.join(cmd))
    ret = os.system(' '.join(cmd))
    if ret != 0:
        print('loading ctrace error')
        exit(-1)

    # load parsed traces
    trace_list = []
    for filename in files:
        parsed_file = trace_path + 'parsed_' + filename
        with open(parsed_file, 'rb') as f:
            fread = f.read
            ctrace_pack = []
            data_read = 0
            while data := fread(18000): # 36 * 500
                data_read += len(data)
                ctrace_pack += [tuple([data[j:j + 4] for j in range(i, i+20, 4)]) + tuple([data[i + 20:i + 28]])
                                + tuple([data[i + 28:i + 36]]) for i in range(0, len(data), 36)]
            # while data := fread(20000): # 40 * 500
            #     data_read += len(data)
            #     ctrace_pack += [tuple([data[j:j + 4] for j in range(i, i+20, 4)]) + tuple([data[i + 24:i + 32]])
            #                     + tuple([data[i + 32:i + 40]]) for i in range(0, len(data), 40)]

        trace_list.append(set(ctrace_pack))
        # print(len(trace_list[-1]))

    final_set_uni = trace_list[0].copy()
    final_set_inter = trace_list[0].copy()
    for trace in trace_list[1:]:
        final_set_uni |= trace
        final_set_inter &= trace

    return {'uni': final_set_uni, 'inter': final_set_inter}


def get_diff_calls(test_path):
    ct1 = load_traces('a', test_path)
    ct2 = load_traces('b', test_path)

    ct1_uni = ct1['uni']
    ct2_uni = ct2['uni']
    ct1_inter = ct1['inter']
    ct2_inter = ct2['inter']

    ct1_only = ct1_inter - ct2_uni
    ct2_only = ct2_inter - ct1_uni

    # get common caller hashes
    ct1_inter_caller_hashes = set([x[6] for x in ct1_inter])
    ct2_inter_caller_hashes = set([x[6] for x in ct2_inter])
    common_caller_hashes = ct1_inter_caller_hashes & ct2_inter_caller_hashes

    # get traces having the common caller hashes from only sets
    div_ct1 = set([x for x in ct1_only if x[6] in common_caller_hashes])
    div_ct2 = set([x for x in ct2_only if x[6] in common_caller_hashes])

    # additionally, include traces having common callee hashes
    ct1_inter_callee_hashes = set([x[5] for x in ct1_inter])
    ct2_inter_callee_hashes = set([x[5] for x in ct2_inter])
    common_callee_hashes = ct1_inter_callee_hashes & ct2_inter_callee_hashes

    # get traces having the common caller hashes from only sets
    div_ct1 |= set([x for x in ct1_only if x[6] in common_callee_hashes])
    div_ct2 |= set([x for x in ct2_only if x[6] in common_callee_hashes])


    div_ct_callers = div_ct1 | div_ct2
    div_ct_callers = {(x[2:4] + tuple([x[6]])) for x in div_ct_callers}

    # get func only data(w/o context) of b for further investigation
    func_only_ct2 = set([x[0:2] for x in (ct1_only | ct2_only)])

    # convert from bytes to int
    bytes_to_int = int.from_bytes

    def convert_to_int(data):
        return [[bytes_to_int(y, 'little') for y in x[:-1]] + [x[-1]] for x in data]

    def convert_to_int2(data):
        return [[bytes_to_int(y, 'little') for y in x] for x in data]

    div_ct_callers = convert_to_int2(div_ct_callers)
    div_ct1 = convert_to_int2(div_ct1)
    div_ct2 = convert_to_int2(div_ct2)
    func_only_ct2 = convert_to_int2(func_only_ct2)

    # draw_diff(div_ct_callers, div_ct1, div_ct2)
    # draw_diff(div_ct_callers, convert_to_int2(ct1_only), convert_to_int2(ct2_only))
    # draw_diff(div_ct_callers, [], convert_to_int2(ct2_uni))
    # draw_diff(div_ct_callers, convert_to_int2(ct1_inter), [])
    # exit()

    # print(len(ct1['uni']), ",", len(ct2['uni']), ",", len(div_ct_callers), end=",")

    # print(len(div_ct1), len(div_ct2))

    return div_ct_callers, div_ct1, div_ct2, func_only_ct2


def draw_diff(div_ct_callers, div_ct1=[], div_ct2=[]):
    from graphviz import Digraph
    g = Digraph('G', filename='output.gv', format="svg")

    g.attr('node', color='green')
    for caller in div_ct_callers:
        caller_str = '%d|%d|%d' % tuple(caller)
        g.node(caller_str)

    def add_edge(g, traces, color='black'):
        g.attr('node', color=color)
        for trace in traces:
            # callee = '%d|%d' % tuple(trace[0:2])
            callee = '%d|%d|%d' % (trace[0], trace[1], trace[5])
            caller = '%d|%d|%d' % (trace[2], trace[3], trace[6])
            g.edge(caller, callee, str(trace[4]), color=color)

    add_edge(g, div_ct1, 'blue')
    add_edge(g, div_ct2, 'red')

    g.view()


