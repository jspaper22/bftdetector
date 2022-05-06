from .bftdetector_option import BFTDetectorOption, PromotionalMethod, BusinessProcessData
from .bftdetector import BFTDetector
import time, multiprocessing


def run_mp_funcs(func, args_list):
    procs = []
    for i in range(3):
        p = multiprocessing.Process(target=func, args=args_list[i])
        procs.append(p)
        p.start()
        time.sleep(3)

    for p in procs:
        p.join()


def tampering_worker(tp_q:multiprocessing.Queue, jsexf: BFTDetector):
    while not tp_q.empty():
        args = tp_q.get()
        if jsexf.terminate_cfmod:
            continue # consume all jobs
        # #jsexf.clear_chrome_cache(args[2])
        jsexf.run_cfmod(args[0], args[1], args[2], args[3], args[4])


class BFTDetectorLauncher:
    def __init__(self, option: BFTDetectorOption, passing: BusinessProcessData, blocking: BusinessProcessData,
                 promotional_method: PromotionalMethod):
        self.option = option
        self.passing_data = passing
        self.blocking_data = blocking
        self.promotional_method = promotional_method

        self.test_inputs = None

    def perform_analysis(self):
        jsexf = BFTDetector(self.option, self.promotional_method)
        jsexf.make_test_dir()

        print('> Performing analysis for Passing side...')
        self.run_analysis_side(self.passing_data, 'a', jsexf)
        print('> Performing analysis for Blocking side...')
        self.run_analysis_side(self.blocking_data, 'b', jsexf)

        print('> Running differential analysis...')
        connected_ct1, connected_ct2 = jsexf.get_ctrace_diff3(draw_ctrace=False)
        self.test_inputs = jsexf.analyze_ctrace_diff_out(connected_ct1, connected_ct2, get_bb_trace=False)

    def start_test(self, test_id_from=0, test_id_to=None, test_id=None):
        jsexf = BFTDetector(self.option, self.promotional_method)
        jsexf.make_test_dir()
        jsexf.clear_chrome_cache()

        if self.test_inputs is None:
            self.test_inputs = jsexf.load_test_inputs()

        if self.test_inputs is None or len(self.test_inputs) == 0:
            return

        test_url = self.blocking_data.pages[0]
        adblock = self.promotional_method == PromotionalMethod.ANTI_ADBLOCKER

        print('> Starting tests...')
        if self.blocking_data.init is not None:
            self.run_init(self.blocking_data.init, jsexf)

        jsexf.init_success_checker()
        process_cnt = jsexf.options.multiprocess_cnt
        tp_q = multiprocessing.Queue()

        if test_id is not None:
            test_id_from = test_id
            test_id_to = test_id

        inst_id = 0
        for indx in range(test_id_from, len(self.test_inputs)):
            if test_id_to is not None and indx > test_id_to:
                break

            tp_q.put([test_url, self.test_inputs[indx], str((inst_id % process_cnt) + 1), indx, adblock])
            inst_id += 1

        time.sleep(0.1)
        print('Tampered Executions')
        print(tp_q.qsize(), 'test inputs')
        # print(tp_indx, 'test inputs')


        procs = []
        for i in range(process_cnt):
            p = multiprocessing.Process(target=tampering_worker, args=(tp_q, jsexf))
            p.start()
            procs.append(p)
            time.sleep(1)

        for p in procs:
            p.join()

        jsexf.clear_chrome_cache()

    def run_clean(self):
        jsexf = BFTDetector(self.option, self.promotional_method)
        test_url = self.blocking_data.pages[0]
        adblock = self.promotional_method == PromotionalMethod.ANTI_ADBLOCKER
        inst_id = None
        if self.blocking_data.init is not None:
            self.run_init(self.blocking_data.init, jsexf)
            inst_id = '1'
        jsexf.run_clean(test_url, inst_id, adblock=adblock, no_close=True, trace_side='b')

    def confirm_test_id(self, test_id):
        jsexf = BFTDetector(self.option, self.promotional_method)
        jsexf.make_test_dir()
        jsexf.clear_chrome_cache()

        if self.test_inputs is None:
            self.test_inputs = jsexf.load_test_inputs()

        if self.test_inputs is None or len(self.test_inputs) == 0:
            return

        test_url = self.blocking_data.pages[0]
        adblock = self.promotional_method == PromotionalMethod.ANTI_ADBLOCKER

        inst_id = None
        if self.blocking_data.init is not None:
            self.run_init(self.blocking_data.init, jsexf)
            inst_id = '1'

        print('> Confirm test id:', test_id, self.test_inputs[test_id])
        jsexf.run_confirm_test(test_url, self.test_inputs[test_id], inst_id, adblock)
        jsexf.clear_chrome_cache()

    def run_init(self, pages, jsexf):
        print('Creating a session...')
        jsexf.run_init(pages, '1')
        jsexf.duplicate_session()

    def run_analysis_side(self, data, side, jsexf):
        jsexf.clear_chrome_cache()

        session = False
        if data.init is not None:
            self.run_init(data.init, jsexf)
            session = True

        if len(data.pages) < 3:
            data.pages += [data.pages[-1]] * (3 - len(data.pages))
        elif len(data.pages) > 3:
            data.pages = data.pages[:3]

        args_list = []
        inst_id = None
        adblock = False
        if self.promotional_method == PromotionalMethod.ANTI_ADBLOCKER and side == 'b':
            adblock = True

        for i in range(len(data.pages)):
            if session:
                inst_id = str(i+1)
            args_list.append((data.pages[i], side, inst_id, adblock,))

        # get html/screenshots
        print('Collecting snapshots...')
        run_mp_funcs(jsexf.run_get_html, args_list=args_list)

        # get dynamic data
        print('Collecting dynamic data...')
        run_mp_funcs(jsexf.run_get_calltrace, args_list=args_list)


class BFTDetectorLauncherAntiAdblocker(BFTDetectorLauncher):
    def __init__(self, option: BFTDetectorOption, page: str):
        self.option = option
        passing_data = BusinessProcessData()
        passing_data.pages = [page]

        blocking_data = BusinessProcessData()
        blocking_data.pages = [page]

        super().__init__(option, passing_data, blocking_data, PromotionalMethod.ANTI_ADBLOCKER)


class BFTDetectorLauncherHardPaywall(BFTDetectorLauncher):
    def __init__(self, option: BFTDetectorOption, login_js, sub_pages, passing_pages=None):
        passing_data = BusinessProcessData()
        passing_data.init = login_js
        if passing_pages:
            passing_data.pages = passing_pages
        else:
            passing_data.pages = sub_pages

        blocking_data = BusinessProcessData()
        blocking_data.pages = sub_pages

        super().__init__(option, passing_data, blocking_data, PromotionalMethod.PAYWALL_HARD)


class BFTDetectorLauncherSoftPaywall(BFTDetectorLauncher):
    def __init__(self, option: BFTDetectorOption, paywall_pages, free_pages):
        passing_data = BusinessProcessData()
        #passing_data.pages = free_pages
        passing_data.pages = paywall_pages

        blocking_data = BusinessProcessData()
        blocking_data.init = paywall_pages
        blocking_data.pages = free_pages

        super().__init__(option, passing_data, blocking_data, PromotionalMethod.PAYWALL_SOFT)


class BFTDetectorLauncherHybridPaywall(BFTDetectorLauncher):
    def __init__(self, option: BFTDetectorOption, free_pages, sub_pages):
        passing_data = BusinessProcessData()
        passing_data.pages = free_pages

        blocking_data = BusinessProcessData()
        blocking_data.pages = sub_pages

        super().__init__(option, passing_data, blocking_data, PromotionalMethod.PAYWALL_HYBRID)