const {test}=require('node:test');
const assert=require('node:assert/strict');
const BranchLoader=require('../gitwatch/static/branch-loader.js');

test('late responses cannot replace choices for a new repository',async()=>{
  const pending=new Map();
  const loader=new BranchLoader(url=>new Promise(resolve=>pending.set(url,resolve)),()=>{});
  const first=loader.load('owner/first');
  const second=loader.load('owner/second');
  pending.get('owner/second')({branches:['release'],default_branch:'release'});
  await second;
  pending.get('owner/first')({branches:['main'],default_branch:'main'});
  await first;
  assert.equal(loader.state.url,'owner/second');
  assert.deepEqual(loader.state.branches,['release']);
});

test('closing or changing the form immediately invalidates an unfinished request',async()=>{
  let resolve;
  const loader=new BranchLoader(()=>new Promise(r=>resolve=r),()=>{});
  const request=loader.load('owner/first');
  loader.reset('owner/new');
  resolve({branches:['main'],default_branch:'main'});
  await request;
  assert.equal(loader.state.url,'owner/new');
  assert.equal(loader.state.loaded,false);
  assert.deepEqual(loader.state.branches,[]);
});

test('errors clear old choices and retry can recover, including empty repositories',async()=>{
  let failure=false,branches=['main'];
  const loader=new BranchLoader(async()=>{if(failure)throw new Error('GitHub unavailable');return {branches,default_branch:'main'};},()=>{});
  await loader.load('owner/project');
  failure=true;
  await loader.load('owner/project');
  assert.equal(loader.state.error,'GitHub unavailable');
  assert.equal(loader.state.loaded,false);
  assert.deepEqual(loader.state.branches,[]);
  failure=false;branches=[];
  await loader.load('owner/project');
  assert.equal(loader.state.loaded,true);
  assert.equal(loader.state.error,'');
  assert.deepEqual(loader.state.branches,[]);
});
