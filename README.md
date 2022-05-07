# BFTDetector
## Demo Videos
+ Bookmate (Hard Paywall)
  + [Testing demo](https://drive.google.com/file/d/1GOJGvRgzhzTidFZDj9ve55gOAEu0HuJx/view?usp=sharing)
  + [Discovered vulnerability](https://drive.google.com/file/d/1Fy-717-xeM4n2-mGEvbOpMtIg6AaLavw/view?usp=sharing)
+ LA Times (Anti-Adblocker)
  + [Testing demo](https://drive.google.com/file/d/1tiQoxNRCIvkAhqKKNZBJL3r65wR-9GMv/view?usp=sharing)
  + [Discovered vulnerability](https://drive.google.com/file/d/1W7JyfLQcGiPqBt6Z2wyywzqnPM_StfJG/view?usp=sharing)

# Installation
BFTDetector is implemented and tested on Ubuntu 20.04 LTS. Any Ubuntu distribution above 16.04 would be fine.
It is highly recommended to use more than 16GB RAM and faster CPU.
+ Dependencies
    ```shell
    sudo apt-get install -y git curl libgtk2.0-0 libgtk-3-0 libnotify-dev libgconf-2-4 libnss3 libxss1 libasound2 libxtst6 xauth xvfb libgbm-dev
    ```
    + Python3
    ```shell
    sudo apt-get install -y python3 pip
    ```
    + NodeJS (>=16.x)
    ```shell
    curl -fsSL https://deb.nodesource.com/setup_16.x | sudo bash - 
    sudo apt-get install -y nodejs
    ```

+ Download repository
	```shell
	git clone https://github.com/jspaper22/bftdetector.git
	```
+ Install via pip
	```shell
	cd bftdetector
	pip install .
	```
 
# Usage

## Examples
Examples can be found in ./examples folder.
+ Anti-adblocker
```python
from bftdetector import BFTDetectorOption
from bftdetector import BFTDetectorLauncherAntiAdblocker

if __name__ == '__main__':
    option = BFTDetectorOption()
    option.test_name = 'latimes'
    page = 'https://www.latimes.com/business/story/2019-12-19/boeing-spacex-spacecraft-parachutes'
    bftd = BFTDetectorLauncherAntiAdblocker(option=option, page=page)
    bftd.perform_analysis()
    bftd.start_test()
```
+ Soft Paywall
```python
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
```
+ Using recorded Puppeteer JS
```python
from bftdetector import BFTDetectorOption
from bftdetector import BFTDetectorLauncherHybridPaywall


if __name__ == '__main__':
    option = BFTDetectorOption()
    option.timeout = 20
    option.test_name = 'bookmate'
    free_pages = ['./bookmate_data/bookmate_free.js']
    sub_pages = ['./bookmate_data/bookmate_sub.js']
    bftd = BFTDetectorLauncherHybridPaywall(option=option, free_pages=free_pages, sub_pages=sub_pages)
    bftd.perform_analysis()
    bftd.start_test()
```

## BFTDetectorOption

| Parameter                    | Default        | Description                                                         |
|------------------------------|----------------|---------------------------------------------------------------------|
| test_name                    | "test"         | Test name.                                                          |
| working_dir                  | "./workingdir" | Base path where testing files are stored (workingdir_dir/test_name) |
| enable_widevine              | False          | Set True if video play is not working                               |
| multiprocess_cnt             | 3              | Process count for multiprocessing                                   |
| timeout                      | 15             | Basic timeout for loading/handling a page                           |
| timeout_callstack_collection | 40             | Extended timeout for dynamic data collection step                   |
| stop_loading_timer           | 30             | Additional timer to prevent endless page loading                    |
| exit_when_succeed            | False          | Exit testing when it finds success case                             |

## APIs
### BFTDetectorLauncherAntiAdblocker(option, page)
+ option:BFTDetectorOption
+ page: str
  + A single page containing anti-adblocker
### BFTDetectorLauncherHardPaywall(option, login_js, sub_pages, passing_pages=None)
+ option:BFTDetectorOption
+ login_js: list
  + Puppeteer js file path(s) for passing run
+ sub_pages: list
  + URLs of pages requiring subscription for both runs
+ passing_pages: list, optional
  + URLs of pages for passing run. If specified, this pages are used for passing test instead of sub_pages.
### BFTDetectorLauncherSoftPaywall(option, paywall_pages, free_pages)
+ option:BFTDetectorOption
+ paywall_pages: list
  + URLs of pages to trigger a paywall. This is also used for passing run.
+ free_pages: list
  + URLs of test pages for blocking run
### BFTDetectorLauncherHybridPaywall(option, free_pages, sub_pages)
+ This is for testing hard paywall with free pages
+ option:BFTDetectorOption
+ free_pages: list
  + URLs of free pages for passing run 
+ sub_pages: list
  + URLs of pages requiring subscription for blocking run.

### Common Methods
+ perform_analysis()
  + Performing dynamic data collection for both passing and blocking runs
+ start_test(test_id_from=0, test_id_to=None, test_id=None):
  + Start series of testing with generated test inputs
    + test_id_from: int
      + Test start id number
    + test_id_to: int or None
      + Test end id number
    + test_id: int or None, default=None
      + If specified, only this test_id is tested
+ run_clean()
  + Launch browser without any modification
+ confirm_test_id(test_id)
  + Confirm tampered execution with the test_id input. Browser is not closed automatically.
    + test_id: int
      + Test id number

## Testing results
For each test, testing result information is displayed with this format:
```
> Test ID:  <###>  [ <Success/Failed> ]
  + JS Source URL: <URL> 
    - <Tampering Action> to branch <##> at (<line #>:<column #>)
    - ...
```
This is an example of the testing result
```
> Test ID:   8  [ Failed ]
  + JS Source URL: https://static.chartbeat.com/js/chartbeat_video.js 
    - Forced execution to branch #1 at (140:1044)
    - Forced execution to branch #0 at (140:772)
    - Forced execution to branch #0 at (140:749)
```
