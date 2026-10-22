import {test} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {inside,readField,review} from './review.mjs';
test('artifact server contains paths after canonical resolution',()=>{
  const root=resolve('fixture');
  assert.equal(inside(root,resolve(root,'index.html')),true);
  assert.equal(inside(root,resolve(root,'../private.txt')),false);
  assert.equal(inside(root,resolve(root,'../fixture-copy/index.html')),false);
  assert.equal(inside(root,root),false);
});
test('download assertions inspect data without executing expressions',()=>{
  assert.equal(readField({reviews:[{decision:'approved'}]},'reviews.0.decision'),'approved');
  assert.equal(readField({reviews:[]},'reviews.length'),0);
  assert.equal(readField({},'missing.path'),undefined);
});
test('browser review rejects external dependencies and runtime failures',async()=>{
  const directory=await mkdtemp(resolve(tmpdir(),'ptp-review-negative-'));
  const output=await mkdtemp(resolve(tmpdir(),'ptp-review-report-'));
  try {
    await writeFile(resolve(directory,'index.html'),'<html lang="en"><head><title>Negative test</title><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="styles.css"></head><body><main><h1>Broken app</h1><button>Action</button></main><script src="app.js"></script></body></html>');
    await writeFile(resolve(directory,'styles.css'),'button:focus-visible{outline:3px solid black}');
    await writeFile(resolve(directory,'app.js'),"fetch('https://example.invalid/forbidden').catch(()=>{}); setTimeout(()=>{throw new Error('intentional runtime failure')},0);");
    const result=await review(directory,output);
    assert.equal(result.status,'FAIL');
    assert.ok(result.blockedRequests.includes('https://example.invalid'));
    assert.ok(result.errors.some(message=>message.includes('intentional runtime failure')));
  } finally {
    assert.ok(inside(resolve(tmpdir()),directory)&&directory.startsWith(resolve(tmpdir(),'ptp-review-negative-')));
    assert.ok(inside(resolve(tmpdir()),output)&&output.startsWith(resolve(tmpdir(),'ptp-review-report-')));
    await rm(directory,{recursive:true,force:true});await rm(output,{recursive:true,force:true});
  }
});
