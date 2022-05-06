import os


class TestInputGenerator:
    def __init__(self):
        self.html = ''

    def head(self):
        self.html += 'exports.test = async function(pb, dumpio, devtool){\n'

    def tail(self):
        self.html += '}'

    def start_browser(self, test_path, inst_id=None):
        args = ''
        if inst_id is not None:
            args = ',["--user-data-dir=%stmpdir/inst%s/chrome_dir"]' % (test_path, inst_id)

        self.html += '\t' + 'await pb.start_browser(dumpio, devtool, true%s);\n' % args

    def bring_front(self):
        self.html += '\t' + 'await pb.page.bringToFront();\n'

    def load_page(self, url):
        self.html += '\t' + 'await pb.load_page("%s", 0);\n' % url

    def close_browser(self):
        self.html += '\t' + 'await pb.close();\n'

    def save_ctrace(self, timeout, add_await=False):
        str_await = ''
        if add_await:
            str_await = 'await '

        self.html += '\t' + str_await + 'pb.saveCTrace(' + str(timeout) + ');\n'

    def dom_monitor(self, selector_list):
        self.html += '\t' + 'await pb.addDOMMonitor(["%s"]);\n' % '","'.join(selector_list)

    def save_result(self, output_name, timeout, add_await=False):
        str_await = ''
        if add_await:
            str_await = 'await '

        self.html += '\t' + '%spb.saveResult("%s", %s);\n' % (str_await, output_name, str(timeout))

    def save_to_file(self, filename, path=None):
        if path is None:
            path = os.getcwd()
        fullpath = path + '/' + filename
        with open(fullpath, 'w') as f:
            f.write(self.html)

        return fullpath

    def save_srcs(self, filepath, timeout, add_await=False):
        str_await = ''
        if add_await:
            str_await = 'await '

        self.html += '\t' + '%spb.saveSrcs("%s", %s);\n' % (str_await, filepath, str(timeout))

    def sleep(self, ms):
        self.html += '\tawait new Promise(r => setTimeout(r, ' + str(ms) +'));\n'

    def timeout_stop(self, timeout):
        self.html += '\tpb.timeout_stop(' + str(timeout) + ');\n'

    def adblock(self):
        self.html += '\tpb.load_adblock = true;\n'

    def enable_widevine(self):
        self.html += '\tawait pb.enableWideVine();\n'

    def click(self, selector):
        self.html += '\tawait pb.page.click("'+ selector +'");\n'

    def scroll(self, distance):
        self.html += '\tawait pb.scrollBy(' + str(distance) + ')\n'

    def eval_js(self, jscode):
        self.html += '\tawait pb.evalJS("' + jscode + '")\n'

    def save_stat(self, timeout):
        self.html += '\tawait pb.saveStat(%s);\n' % str(timeout)

    def inject_puppet_js(self, js_filename):
        # parse puppeteer script recorded by chrome dev tool
        js=''
        with open(js_filename, 'r') as f:
            js = f.read()

        actions = js.split('{\n        const targetPage = page;')
        if len(actions) < 2:
            print('Parsing input js file failed: ', js_filename)
            exit()

        output = []
        actions[-1] = actions[-1].split('await browser.close();')[0]
        for action in actions[1:]:
            output.append('{\n        const targetPage = page;'
                          + action
                          + 'await new Promise(r => setTimeout(r, 1000));')

        self.html += '\n' + FUNCS_FOR_RECORDED_JS + '\n' + '\n'.join(output) + '\n'

    def make_simple_visit(self, page, opt, inst_id=None, ctrace_mode=False, dom_monitor=None
                          , save_result=None, save_srcs=None, adblock=False, no_close=None, trace_side=None
                          , stat_mode=False):
        test_path = opt.working_dir + opt.test_name + '/'
        self.html = ''

        self.head()
        if adblock:
            self.adblock()

        self.start_browser(inst_id=inst_id, test_path=test_path)

        # timeout_added = 0

        if opt.enable_widevine:
            self.enable_widevine()
            # self.sleep(10000)
            # timeout_added += 10

        if adblock:
            self.sleep(3000)
            # timeout_added += 3

        self.bring_front()
        if dom_monitor:
            self.dom_monitor(dom_monitor)

        timeout = (opt.timeout + 0) * 1000
        if save_result:
            self.save_result(save_result, timeout)
        if save_srcs:
            self.save_srcs(save_srcs, timeout)
        if ctrace_mode:
            self.save_ctrace(timeout)
        if stat_mode:
            self.save_stat(timeout)

        if page[:4] == 'http':
            self.load_page(page)
        else:
            self.inject_puppet_js(page)

        self.sleep(1000)

        if opt.simple_click is not None:
            click_data = opt.simple_click
            if type(opt.simple_click) == dict and trace_side is not None:
                click_data = opt.simple_click[trace_side]

            if type(click_data) == list:
                for selectors in click_data:
                    self.click(selectors)
                    self.sleep(1500)
            else:
                self.click(click_data)

        if opt.scroll_on_load is not None:
            self.scroll(opt.scroll_on_load)

        if opt.js_on_load is not None:
            self.eval_js(opt.js_on_load)

        if (no_close is not True) and (not stat_mode) and (save_result is None and save_srcs is None and not ctrace_mode and dom_monitor is None):
            self.close_browser()

        self.tail()

        path = test_path + 'tmpdir'
        if inst_id:
            path += '/inst' + inst_id

        return self.save_to_file(filename='testjs.js', path=path)

        # return self.html

    def make_init_script(self, pages, opt, inst_id=None, ):
        test_path = opt.working_dir + opt.test_name + '/'
        self.html = ''

        self.head()

        self.start_browser(inst_id=inst_id, test_path=test_path)

        if opt.enable_widevine:
            self.enable_widevine()

        self.bring_front()

        for page in pages:
            if page[:4] == 'http':
                self.load_page(page)
            else:
                self.inject_puppet_js(page)

            self.sleep(1000)



        self.tail()

        path = test_path + 'tmpdir'
        if inst_id:
            path += '/inst' + inst_id

        return self.save_to_file(filename='testjs.js', path=path)



FUNCS_FOR_RECORDED_JS = """
    const page = pb.page;
    const timeout = 15000;

    async function waitForSelectors(selectors, frame, options) {
      for (const selector of selectors) {
        try {
          return await waitForSelector(selector, frame, options);
        } catch (err) {
          console.error(err);
        }
      }
      throw new Error('Could not find element for selectors: ' + JSON.stringify(selectors));
    }

    async function scrollIntoViewIfNeeded(element, timeout) {
      await waitForConnected(element, timeout);
      const isInViewport = await element.isIntersectingViewport({threshold: 0});
      if (isInViewport) {
        return;
      }
      await element.evaluate(element => {
        element.scrollIntoView({
          block: 'center',
          inline: 'center',
          behavior: 'auto',
        });
      });
      await waitForInViewport(element, timeout);
    }

    async function waitForConnected(element, timeout) {
      await waitForFunction(async () => {
        return await element.getProperty('isConnected');
      }, timeout);
    }

    async function waitForInViewport(element, timeout) {
      await waitForFunction(async () => {
        return await element.isIntersectingViewport({threshold: 0});
      }, timeout);
    }

    async function waitForSelector(selector, frame, options) {
      if (!Array.isArray(selector)) {
        selector = [selector];
      }
      if (!selector.length) {
        throw new Error('Empty selector provided to waitForSelector');
      }
      let element = null;
      for (let i = 0; i < selector.length; i++) {
        const part = selector[i];
        if (element) {
          element = await element.waitForSelector(part, options);
        } else {
          element = await frame.waitForSelector(part, options);
        }
        if (!element) {
          throw new Error('Could not find element: ' + selector.join('>>'));
        }
        if (i < selector.length - 1) {
          element = (await element.evaluateHandle(el => el.shadowRoot ? el.shadowRoot : el)).asElement();
        }
      }
      if (!element) {
        throw new Error('Could not find element: ' + selector.join('|'));
      }
      return element;
    }

    async function waitForElement(step, frame, timeout) {
      const count = step.count || 1;
      const operator = step.operator || '>=';
      const comp = {
        '==': (a, b) => a === b,
        '>=': (a, b) => a >= b,
        '<=': (a, b) => a <= b,
      };
      const compFn = comp[operator];
      await waitForFunction(async () => {
        const elements = await querySelectorsAll(step.selectors, frame);
        return compFn(elements.length, count);
      }, timeout);
    }

    async function querySelectorsAll(selectors, frame) {
      for (const selector of selectors) {
        const result = await querySelectorAll(selector, frame);
        if (result.length) {
          return result;
        }
      }
      return [];
    }

    async function querySelectorAll(selector, frame) {
      if (!Array.isArray(selector)) {
        selector = [selector];
      }
      if (!selector.length) {
        throw new Error('Empty selector provided to querySelectorAll');
      }
      let elements = [];
      for (let i = 0; i < selector.length; i++) {
        const part = selector[i];
        if (i === 0) {
          elements = await frame.$$(part);
        } else {
          const tmpElements = elements;
          elements = [];
          for (const el of tmpElements) {
            elements.push(...(await el.$$(part)));
          }
        }
        if (elements.length === 0) {
          return [];
        }
        if (i < selector.length - 1) {
          const tmpElements = [];
          for (const el of elements) {
            const newEl = (await el.evaluateHandle(el => el.shadowRoot ? el.shadowRoot : el)).asElement();
            if (newEl) {
              tmpElements.push(newEl);
            }
          }
          elements = tmpElements;
        }
      }
      return elements;
    }

    async function waitForFunction(fn, timeout) {
      let isActive = true;
      setTimeout(() => {
        isActive = false;
      }, timeout);
      while (isActive) {
        const result = await fn();
        if (result) {
          return;
        }
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      throw new Error('Timed out');
    }
"""