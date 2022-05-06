from bftdetector import BFTDetectorOption
from bftdetector import BFTDetectorLauncherAntiAdblocker

if __name__ == '__main__':
    option = BFTDetectorOption()
    option.test_name = 'latimes'
    page = 'https://www.latimes.com/business/story/2019-12-19/boeing-spacex-spacecraft-parachutes'
    bftd = BFTDetectorLauncherAntiAdblocker(option=option, page=page)
    bftd.perform_analysis()
    bftd.start_test()