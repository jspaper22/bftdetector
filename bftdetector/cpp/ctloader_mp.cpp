#include <iostream>
#include <fstream>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#include <thread>
#include <mutex>
#include <cstdint>

#define XXH_INLINE_ALL
#include "xxhash.h"

using namespace std;

struct CallTracePack {
  int data[5];
  uint64_t hash[2];
};

struct RawTraceItem {
  char* pRawData;
  int traceCnt;
};

const size_t INT_SIZE = sizeof(int);
const size_t CTP_FULL_SIZE = 40;
 const int NUM_WORKER = 32;
//const int NUM_WORKER = 1;

mutex mtx;

void trace_worker(vector<RawTraceItem> rawTraceList, map<uint64_t, CallTracePack> *retMap){
  map<uint64_t, CallTracePack> ctracePackMap;
    
  int* pTrace;
  int* pCaller;
  int* pCallee;
  int* pCallPos;
  char hashBuf[4 * 102400];
  int curContextPoint;
  size_t hashBufSize;
  uint64_t calleeHash;
  uint64_t callerHash;

  uint64_t packHash;

  vector<uint64_t> packHashList;
  vector<CallTracePack> ctracePackList;

  for(auto &rawTraceItem : rawTraceList){
    if(rawTraceItem.traceCnt < 6)
        continue;

    pTrace = (int*)rawTraceItem.pRawData;
    // initial callee hash = full hash
    hashBufSize = (rawTraceItem.traceCnt - 3) * INT_SIZE;
    memcpy(hashBuf, pTrace, 2*INT_SIZE);
    memcpy(hashBuf + (2 * INT_SIZE), pTrace + 3, hashBufSize);
    callerHash = XXH3_64bits((const void*)hashBuf, hashBufSize + (2 * INT_SIZE));

    pCaller = pTrace;

    for(int i=3; i+3<rawTraceItem.traceCnt; i+=3){
      calleeHash = callerHash;
      pCallee = pCaller;
      pCaller = pTrace + i;
      pCallPos = pTrace + i + 2;

      curContextPoint = i+3;
      hashBufSize = (rawTraceItem.traceCnt - curContextPoint) * INT_SIZE;
      memcpy(hashBuf, pCaller, 2*INT_SIZE);

//      cout << rawTraceItem.traceCnt << "," << curContextPoint << endl;

      memcpy(hashBuf + (2 * INT_SIZE), pTrace + curContextPoint, hashBufSize);
      callerHash = XXH3_64bits((const void*)hashBuf, hashBufSize + (2 * INT_SIZE));


      CallTracePack ctp;
      ctp.data[0] = pCallee[0];
      ctp.data[1] = pCallee[1];
      ctp.data[2] = pCaller[0];
      ctp.data[3] = pCaller[1];
      ctp.data[4] = *pCallPos;
      ctp.hash[0] = calleeHash;
      ctp.hash[1] = callerHash;
      packHash = XXH3_64bits((const void*)&ctp, CTP_FULL_SIZE);

      //cout << " " << packHash << endl;
      auto it = lower_bound(packHashList.begin(), packHashList.end(), packHash);
      if (it != packHashList.end() && *it == packHash)
        continue;

      packHashList.insert(it, packHash);
//      cout << packHashList.size() << endl;
      ctracePackMap[packHash] = ctp;
      //cout << ctracePackMap.size() << "," << ctracePackMap.max_size() << "," << packHashList.size() << endl;
      // cout <<   (uint32_t)ctp.data[0] << " " << (uint32_t)ctp.data[1] << " " << (uint32_t)ctp.data[2] << " " << (uint32_t)ctp.data[3] << " " << (uint32_t)ctp.data[4] << " " << ctp.hash;
      // cout << endl;

    }
  }
  
  mtx.lock();  
  retMap->insert(ctracePackMap.begin(), ctracePackMap.end());
  mtx.unlock();

//   cout << ctracePackMap.size() << endl;

}

void load_ctrace(string basepath, vector<string> filenames){

  for(auto &filename: filenames){
    ifstream rf((basepath + filename).data(), ios::out | ios::binary);
    if(!rf) {
        cout << "Cannot open file!" << endl;
        exit(1);
    }

    // read raw data from file
    vector<RawTraceItem> rawTraceList;
    int traceCnt;
    int i=0;
    while(rf.read((char *) &traceCnt, INT_SIZE)){
      if(traceCnt < 0)
        break;
      if(traceCnt > 20000)
        break;

      RawTraceItem rti;
      rti.traceCnt = traceCnt;

      rti.pRawData = new char[INT_SIZE * traceCnt];
      rf.read((char *) rti.pRawData, INT_SIZE * traceCnt);
      rawTraceList.push_back(rti);
    }

    rf.close();

    // prepare input data for each threads
    int numWorker = NUM_WORKER;
    if(rawTraceList.size() < numWorker)
      numWorker = 1;

    size_t dataCntPerThread = rawTraceList.size() / numWorker;
    vector<vector<RawTraceItem>> dataPerThreadList(numWorker);
    int indx;
    for(indx=0;indx<numWorker;indx++){    
      auto& vec = dataPerThreadList[indx];
      size_t last = dataCntPerThread * (indx+1);
      if(indx == numWorker - 1)
        last = rawTraceList.size();

      vec.reserve(last - (dataCntPerThread * indx));
      move(rawTraceList.begin() + (dataCntPerThread * indx), rawTraceList.begin() + last, back_inserter(vec));
    }

    map<uint64_t, CallTracePack> *retCTPMap = new map<uint64_t, CallTracePack>();

    // start worker threads
    vector<thread> threads;
    for(int i=0;i<numWorker;i++){
      threads.push_back( thread(trace_worker, dataPerThreadList[i], retCTPMap) );
    }

    for (auto &th : threads){
      th.join();
    }

    for(auto &rawTrace: rawTraceList)
      delete[] rawTrace.pRawData;

    // save result to file
    string output_path = basepath + "parsed_" + filename;
    ofstream wf(output_path.data(), ios::out | ios::binary);
    for (const auto& ctPackMap : *retCTPMap) {
      CallTracePack ctracePack = ctPackMap.second;
      wf.write(reinterpret_cast<char *>(ctracePack.data), INT_SIZE * 5);
      wf.write(reinterpret_cast<char *>(ctracePack.hash), 8 * 2);
    }
    wf.close();

    delete retCTPMap;

//     cout << retCTPMap->size() << endl;
    // cout << CTP_SIZE << endl;
  }  
}



int main(int argc, char *argv[]){
  if(argc < 3)
    exit(1);

  string basepath(argv[1]);
  vector<string> filenames;
  for(int i=0;i<argc-2;i++)
    filenames.push_back(argv[i+2]);  

  load_ctrace(basepath, filenames);
  

  return 0;
}
