from bftdetector import BFTDetectorOption
from bftdetector import BFTDetectorLauncherHybridPaywall

if __name__ == '__main__':
    option = BFTDetectorOption()
    option.timeout = 20
    option.timeout_callstack_collection = 50
    option.test_name = 'bookmate'
    free_pages = ['./bookmate_data/bookmate_free.js']
    sub_pages = ['./bookmate_data/bookmate_sub.js']
    bftd = BFTDetectorLauncherHybridPaywall(option=option, free_pages=free_pages, sub_pages=sub_pages)
    bftd.perform_analysis()
    bftd.start_test()
