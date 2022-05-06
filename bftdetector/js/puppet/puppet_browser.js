"use strict"

const puppeteer = require('puppeteer');
const fs = require('fs');
const { spawnSync } = require( 'child_process' );
const PythonShell = require('python-shell');
const util = require('util');
const murmurhash3 = require('./murmurhash3');

const options = {
    ignoreAttributes: [],
    compareAttributesAsJSON: [],
    ignoreWhitespaces: true,
    ignoreComments: true,
    ignoreEndTags: false,
    ignoreDuplicateAttributes: false
};

const writeFile = util.promisify(fs.writeFile);
const appendFile = util.promisify(fs.appendFile);

function PuppetBrowser(){
    this.mod_chrome_path = null;
    this.working_dir = null;
    this.inst_id = null;

    this.browser = null;
    this.page = null;
    this.dom_track = true;
    this.load_adblock = false;

    this.selector = '';

    this.processing = 0;
    this.test_mode = '';

    this.scripts_downloaded = {};

    this.timeout_stop_timer = null;

    this.v8cfg = null;

    this.getInstDir = function(){
        if(this.inst_id)
            return this.getTmpDir() + 'inst' + this.inst_id + '/';
        else
            return this.getTmpDir();
    }

    this.getTmpDir = function(){
        return this.working_dir + 'tmpdir/';
    }

    this.enableInterceptConsole = function(intercept_all_console){
        if(intercept_all_console) {
            this.page.on('console', msg => {
                if(msg._text.indexOf('>>PUPPET:') !== -1){
                    console.log(msg._text);
                }
                if(msg._text.indexOf('>>RUNTIME:') !== -1)
                    console.log(msg._text);
                if(msg._text.indexOf('>>EVENT_INFO:') !== -1)
                    console.log(msg._text);
                if(msg._type === 'trace'){
                    this.printCallStack(msg._text);
                }
            });
        } else {
            this.page.on('console', msg => {
                if (msg._text.indexOf('>>PUPPET:') !== -1) {
                    console.log(msg._text);
                }
            });
        }
    };

    this.setRecentAgentHeader = async function(){
        let agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4940.0 Safari/537.36';
        await this.page.setUserAgent(agent);
    };

    this.start_browser = async function(dumpio = true, devtools = true, intercept_all_console = true, args = []){
        process.chdir(this.getInstDir());
        await this.loadV8Cfg();

        args.push('--no-sandbox', '--mute-audio');
        if(this.load_adblock)
            args.push('--load-extension=' + __dirname + '/adblock/', '--disable-extensions-except=' + __dirname + '/adblock/');

        let params = {headless: false, args: args, ignoreHTTPSErrors: true, devtools:devtools, dumpio:dumpio};
        params.executablePath = this.mod_chrome_path;
        params.defaultViewport = {width:1200, height:900};

        this.browser = await puppeteer.launch(params);
        let pages = await this.browser.pages();
        this.page = await pages[0];

        await this.setRecentAgentHeader();
        let page = this.page;

        this.enableInterceptConsole(intercept_all_console);
        // await page.setViewport({"width":1200,"height":900})

        await this.sleep(1000);
    };

    this.load_page = async function(url, timeout = 300000, selectorForWait = null, selectorVisible = true){
        await this.page.goto(url, {timeout:timeout});
        if(selectorForWait != null){
            await this.page.waitForSelector(selectorForWait, {visible: selectorVisible})
        }
    };

    this.addDOMMonitor = async function(selectors){
        await this.page.evaluateOnNewDocument((selectors) => {
            let config = { attributes: true, characterData: true, childList: true, subtree: true};
            let callback = function(mutationsList) {
                for(let mutation of mutationsList) {
                    let node = mutation.target;
                    let doc = node.ownerDocument;
                    if(doc == null)
                        return;
                    for(let selector of selectors) {
                        let targetNode = doc.querySelector(selector);
                        if(targetNode != null && (targetNode.contains(node) || targetNode === node)){
                            console.trace();
                        }
                    }
                }
            };

            // Create an observer instance linked to the callback function
            let observer = new MutationObserver(callback);

            // Start observing the target node for configured mutations
            observer.observe(document, config);

        }, selectors);
    };

    this.interceptFile = async function(url, filename){
        await this.page.setRequestInterception(true);
        this.page.on('request', request => {

            if(request.resourceType() === 'script'){
                if( request._url === url){
                    console.log(request._url);
                    const modified_js = fs.readFileSync(filename, 'utf8');
                    request.respond({
                        status: 200,
                        contentType: 'text/javascript',
                        body: modified_js
                    });
                    return;
                }
            }
            request.continue();
        });
    }

    this.close = function(pb = this){
        if(this.timeout_stop_timer)
            clearTimeout(this.timeout_stop_timer);

        if(pb.processing !== 0){
            setTimeout(this.close, 2000, pb);
        } else {
            setTimeout((pb) => {pb.browser.close();}, 5000, pb);
        }
    }

    this.enableWideVine = async function(){
        await this.page.goto('chrome:components');
        let elem = await this.page.$('#version-oimompecagnajdejgnnjijobebaeigek');
        let version = await (await elem.getProperty('innerText')).jsonValue();
        if(version === '0.0.0.0') {
            await this.page.click('#oimompecagnajdejgnnjijobebaeigek');

            await new Promise(resolve => {
                let timer = setInterval(async ()=>{
                    let version = await (await elem.getProperty('innerText')).jsonValue();
                    if(version !== '0.0.0.0') {
                        clearInterval(timer);
                        resolve();
                    }
                }, 500);
            });
        }
    }

    this.downloadJS = async function(scripts){
        this.processing += 1;

        // download scripts
        await this.page._client.send('Debugger.enable');
        for(let scriptId in scripts){
            // console.log(scriptId, scripts);
            let source_url = scripts[scriptId];
            let hash = murmurhash3(source_url, 0);
            const path = this.getTmpDir() + 'tempjs/' + hash + '.js';
            try {
                if (fs.existsSync(path)) {
                    continue;
                }
            } catch(err) {
                console.error(err);
                continue;
            }

            if (source_url === this.page.url()){
                // just store this page
                let html = await this.page.content();
                await writeFile(path, html);
                // continue;
            } else {
                let res = await this.page._client.send('Debugger.getScriptSource', {'scriptId':scriptId});
                if(!(hash in this.scripts_downloaded)){
                    this.scripts_downloaded[hash] = source_url;
                    // console.log('[' + Object.keys(this.scripts_downloaded).join(',') + ']');
                }
                await writeFile(path, res.scriptSource);
            }
            // console.log(hash, source_url);
            await appendFile(this.getTmpDir() + 'tempjs/scripts.log', hash + '\t' + source_url + '\n');
        }
        this.processing -= 1;
    };

    this.saveSrcs = async function(filepath, timeout){
        setTimeout(async()=> {
            await this.saveHTML(filepath + '.html');
            await this.saveScreenshot(filepath + '.jpg');
            if(timeout !== 0)
                await this.close();
        }, timeout);
    }

    this.saveHTML = async function(filepath){
        let html = await this.page.content();
        fs.writeFile(filepath, html, (err) => {
            if (err) throw err;
        });
    };

    this.saveScreenshot = async function(filepath){
        let opt = {path:filepath, type:'jpeg', quality:100};
        await this.page.screenshot(opt);
    }

    this.saveCTrace = async function(timeout){
        setTimeout(async()=> {
            await this.page.evaluate(() => {
                function v8mod_save_ctrace() {
                }
                v8mod_save_ctrace();
            });

            await this.sleep(6000);

            // save current HTML page
            let output_path = this.getInstDir();

            let logId = this.v8cfg['arg'];

            // await this.saveHTML(output_path + logId + '.html');
            await this.saveAllJSFromCTLog(output_path + '/jshash2_' + logId + '.log');

            await this.close();

        }, timeout);
    };

    this.saveAllJSFromCTLog = async function(log_filename){
        // get js hashes
        let js_hash_data = [];
        try {
            const jslogfile = fs.readFileSync(log_filename, 'utf8');
            let lines = jslogfile.split('\n');
            for(let line of lines){
                let items = line.split('\t');
                if(items.length === 3)
                    js_hash_data.push(items);
            }
        } catch (e) {
            console.log('Failed to read js log file', log_filename);
            return;
        }

        this.processing += 1;
        await this.page._client.send('Debugger.enable');
        for(let hash_data of js_hash_data){
            // console.log(hash_data);
            let source_url = hash_data[1];
            let hash = hash_data[0];
            let scriptId = hash_data[2];

            if(hash === '0')
                continue;
            // if(source_url === '\'__puppeteer_evaluation_script__\'')
            //     continue;

            const path = this.getTmpDir() + 'tempjs/' + hash + '.js';
            try {
                if (fs.existsSync(path)) {
                    continue;
                }
            } catch(err) {
                console.error(err);
                continue;
            }
            if (source_url === this.page.url()){
                // just store this page
                let html = await this.page.content();
                await writeFile(path, html);
                // continue;
            } else {
                try {
                    let res = await this.page._client.send('Debugger.getScriptSource', {'scriptId': scriptId});
                    await writeFile(path, res.scriptSource);
                } catch (e) {
                    console.error('Failed to save script ID:',scriptId);
                    continue;
                }
            }
            // console.log(hash, source_url);
            await appendFile(this.getTmpDir() + 'tempjs/scripts.log', hash + '\t' + source_url + '\n');
        }
        this.processing -= 1;
    }

    this.resetCTrace = async function(){
        await this.page.evaluate(() => {
            function v8mod_reset_ctrace(){}v8mod_reset_ctrace();
        });
    };

    this.printCallStack2 = function(data){
        this.processing += 1;
        data = JSON.parse(data);

        let dataitem = data;
        let first_one = true;
        let scripts = {};

        while(true) {
            let frames = dataitem.callFrames;

            for(let i=0;i<frames.length;i++){
                if(first_one){
                    first_one = false;
                    continue;
                }
                let stack_item = frames[i];
                let source_url = stack_item.url;
                let scriptId = stack_item.scriptId;

                scripts[scriptId] = source_url;
            }

            if(!dataitem.hasOwnProperty('parent'))
                break;
            dataitem = dataitem.parent;
        }

        this.downloadJS(scripts);

        this.processing -= 1;

        // console.log(scripts);
    };

    this.printCallStack = function(data){
        this.processing += 1;
        data = JSON.parse(data);

        let dataitem = data;
        let json_str = "[";
        let first_one = true;
        let stacks = [];

        let scripts = {};

        while(true) {
            let frames = dataitem.callFrames;

            for(let i=0;i<frames.length;i++){
                if(first_one){
                    first_one = false;
                    continue;
                }
                let stack_item = frames[i];
                let pos = (stack_item.lineNumber+1) + ":" + (stack_item.columnNumber+1);
                let source_url = stack_item.url;
                let scriptId = stack_item.scriptId;

                //TODO: change this
                if (source_url === this.page.url()){
                    continue;
                }

                scripts[scriptId] = source_url;

                let fname = stack_item.functionName === ""?"(anonymous)":stack_item.functionName;
                // console.debug(fname + ' at (' + pos + ') ' + source_url);
                let stack = '{"function_name":"'+ fname +'", "position":"' + pos + '", "source_url":"'+source_url+'"}';
                stacks.push(stack);
            }

            if(!dataitem.hasOwnProperty('parent'))
                break;
            dataitem = dataitem.parent;
        }

        console.log('[' + stacks.join(',') +']');

        this.downloadJS(scripts);

        this.processing -= 1;
    };

    this.enableJSTracking = async function(){
        await this.page.setRequestInterception(true);
        const fstream = fs.createWriteStream("script_load.log", {flags: 'w'});

        this.page.on('request', interceptedRequest => {

            if(interceptedRequest.resourceType() === 'script'){
                //let timestamp = Math.floor(Date.now() / 1000);
                let url = interceptedRequest.url();

                fstream.write(url + "\n");
            }
            interceptedRequest.continue();
        });
    };

    this.saveResult = async function(test_output, time){
        if(test_output !== null){
            setTimeout(async()=>{
                let base_path = this.working_dir + 'test_out/'
                let opt = {path:base_path + 'screenshot/' + test_output + '.jpg', type:'jpeg', quality:100};
                await this.page.screenshot(opt);

                let src = await this.page.content();
                fs.writeFile(base_path + 'html/' + test_output + '.html', src, async (err) => {
                    if(err) {
                        return console.log(err);
                    }
                    await this.close();
                });

            }, time);
        }
    };

    this.timeout_stop = function(timeout){
        this.timeout_stop_timer = setTimeout(async()=> {
            // console.log('stop');
            await this.page.evaluate(() => {
                window.stop();
            });
            this.timeout_stop_timer = null;
        }, timeout);
    }

    this.sleep = function(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    this.loadV8Cfg = async function(){
        let lines = fs.readFileSync('./v8mod.cfg', 'utf8').split('\n');
        let v8cfg = {};
        for(let line of lines){
            if(line === '')
                break;
            let items = line.split('=');
            v8cfg[items[0]] = items[1];
        }

        this.v8cfg = v8cfg;
        // console.log(v8cfg);
    }

    this.scrollBy = async function(dist){
        await this.page.evaluate((dist) => {
            window.scrollBy(0, dist);
        }, dist);
    }

    this.click = async function(selector){
        await this.page.evaluate((selector) => {
            document.querySelector(selector).click();
        }, selector);
    }

    this.evalJS = async function(jscode){
        await this.page.evaluate((jscode) => {
            eval(jscode);
        }, jscode);
    }

    this.saveStat = async function(timeout){
        setTimeout(async()=> {
            await this.page.evaluate(() => {
                function v8mod_save_stat() {
                }
                v8mod_save_stat();
            });

            await this.sleep(3000);

            await this.close();
        }, timeout);
    }

}

module.exports = PuppetBrowser;