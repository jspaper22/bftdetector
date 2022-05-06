from bftdetector import BFTDetectorOption
from bftdetector import BFTDetectorLauncherSoftPaywall

if __name__ == '__main__':
    option = BFTDetectorOption()
    option.test_name = 'troyrecord'
    paywall_pages = [
        'https://www.troyrecord.com/2022/03/24/a-stunning-dear-evan-hansen-plays-proctors/',
        'https://www.troyrecord.com/2022/03/23/jackson-heading-for-likely-confirmation-despite-gop-darts/',
        'https://www.troyrecord.com/2022/03/23/madeleine-albright-1st-female-us-secretary-of-state-dies/'
    ]
    free_pages = [
        'https://www.troyrecord.com/2022/03/23/biden-seeks-new-sanctions-help-for-ukrainians-in-europe/',
        'https://www.troyrecord.com/2022/03/23/pandemic-relief-money-spent-on-hotel-ballpark-ski-slopes/',
        'https://www.troyrecord.com/2022/03/23/back-on-track-the-flying-horses-are-eager-to-get-back-in-the-swing-of-things-in-2022/'
    ]

    bftd = BFTDetectorLauncherSoftPaywall(option=option, paywall_pages=paywall_pages, free_pages=free_pages)
    bftd.perform_analysis()
    bftd.start_test()

