import multiprocessing
import time
import xxhash
import pickle

hasher = xxhash.xxh3_64_intdigest

NUM_OF_PROCS = 32

def trace_worker(ct_jobs, q):
    my_list = []
    add_to_list = my_list.append
    for ct_job in ct_jobs:
        ct, trace_cnt = ct_job
        caller = ct[0:8]
        for i in range(12, trace_cnt * 4, 12):
            callee = caller
            caller = ct[i:i + 8]
            call_pos = ct[i + 8:i + 12]
            context = caller + ct[i + 12:]
            context_hash = hasher(context)
            add_to_list((callee[0:4], callee[4:8], caller[0:4], caller[4:8], call_pos, context_hash))
            # print(int.from_bytes(callee[0:4], 'little'), int.from_bytes(callee[4:8], 'little'), int.from_bytes(caller[0:4], 'little'), int.from_bytes(caller[4:8], 'little'), int.from_bytes(call_pos, 'little'), context_hash)

    q.put(set(my_list))


def parse_ctrace(filepaths, output_path):
    trace_list = []

    for filepath in filepaths:
        s=time.time()
        print(filepath)

        # a=0
        ct_data = []
        ct_data_append = ct_data.append
        with open(filepath, 'rb') as f:
            fread = f.read
            while data := fread(4):
                trace_cnt = int.from_bytes(data, 'little')
                print(trace_cnt)
                ct = fread(trace_cnt * 4)
                ct_data_append((ct, trace_cnt))
                # a+=1
                # if a>10:
                #     break



        num_of_proc = NUM_OF_PROCS
        if len(ct_data) < num_of_proc:
            num_of_proc = len(ct_data)

        jobs_per_proc = int(len(ct_data) / num_of_proc)
        ct_jobs = [ct_data[i:i + jobs_per_proc] for i in range(0, jobs_per_proc * num_of_proc, jobs_per_proc)]
        ct_jobs[0] += ct_data[jobs_per_proc * num_of_proc:]

        procs = []
        ret_queue = multiprocessing.Queue()
        for i in range(num_of_proc):
            p = multiprocessing.Process(target=trace_worker, args=(ct_jobs[i], ret_queue,))
            p.start()
            procs.append(p)

        final_list = []
        for p in procs:
            final_list.append(ret_queue.get())

        final_set = final_list[0]
        for l in final_list[1:]:
            final_set |= l

        trace_list.append(final_set)


        print(len(final_set))
        print(time.time()-s)

    final_set_uni = trace_list[0].copy()
    final_set_inter = trace_list[0].copy()
    for trace in trace_list[1:]:
        final_set_uni |= trace
        final_set_inter &= trace

    calltrace = {'uni': final_set_uni, 'inter': final_set_inter}
    with open(output_path + 'parsed_ctrace.pkl', 'wb') as f:
        pickle.dump(calltrace, f)
