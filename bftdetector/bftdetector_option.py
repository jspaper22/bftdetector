
class BusinessProcessData:
    def __init__(self):
        self.init = None
        self.pages = []


class PromotionalMethod:
    UNDEFINED = 0
    ANTI_ADBLOCKER = 1
    PAYWALL_SOFT = 2
    PAYWALL_HARD = 3
    PAYWALL_HYBRID = 4


class BFTDetectorOption:
    def __init__(self):
        self.working_dir = './workingdir'
        self.test_name = 'test'
        self.enable_widevine = False
        self.multiprocess_cnt = 3

        # timers
        self.stop_loading_timer = 30
        self.timeout = 15
        self.timeout_callstack_collection = 40

        self.exit_when_succeed = False

        self.simple_click = None
        self.scroll_on_load = None
        self.js_on_load = None
