from bftdetector import BFTDetectorOption
from bftdetector import BFTDetectorLauncherSoftPaywall

if __name__ == '__main__':
    option = BFTDetectorOption()
    option.test_name = 'time'

    paywall_pages = [
        'https://time.com/6249393/the-modi-question-documentary-bbc-india-controversy/',
        'https://time.com/6249863/presidents-classified-documents-misplaced-history/',
        'https://time.com/6249941/ukraine-corruption-resignation-zelensky-russia/'
    ]

    free_pages = [
        'https://time.com/6248644/hakeem-jeffries-leadership-kappa-alpha-psi-fraternity/',
        'https://time.com/6249068/martin-luther-king-sculpture-hank-willis-thomas-interview/',
        'https://time.com/6249168/lunar-new-year-shooting-monterey-park/'
    ]

    bftd = BFTDetectorLauncherSoftPaywall(option=option, paywall_pages=paywall_pages, free_pages=free_pages)
    bftd.perform_analysis()
    bftd.start_test()