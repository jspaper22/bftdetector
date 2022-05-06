from bftdetector import BFTDetectorOption
from bftdetector import BFTDetectorLauncherAntiAdblocker

if __name__ == '__main__':
    option = BFTDetectorOption()
    option.test_name = 'ocregister'
    page = 'https://www.ocregister.com/2021/02/09/orange-countys-coronavirus-metrics-further-ease-since-new-year-spike/'
    bftd = BFTDetectorLauncherAntiAdblocker(option=option, page=page)
    bftd.perform_analysis()
    bftd.start_test()