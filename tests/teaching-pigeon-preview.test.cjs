const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('docs/mockups/teaching-pigeon-3d-preview.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
function setup() {
  const ids={}, timeouts=new Map(); let next=0, intervals=0;
  function el(id) {
    return ids[id] ??= {value:id==='nameInput'?'Bird':'',checked:false,
      style:{setProperty(){}},classList:{add(){},remove(){}},
      addEventListener(k,f){this[k]=f;},getContext(){return {fillRect(){}};}};
  }
  vm.runInNewContext(source,{
    document:{hidden:false,getElementById:el,querySelectorAll:()=>[],addEventListener(){}},
    matchMedia:()=>({matches:true,addEventListener(){}}),
    setTimeout(f){timeouts.set(++next,f);return next;},clearTimeout(i){timeouts.delete(i);},
    setInterval(){intervals++;},clearInterval(){}
  });
  el('simHatch').onclick();
  return {el,intervals:()=>intervals,expire(){const callbacks=[...timeouts.values()];timeouts.clear();callbacks.forEach(f=>f());}};
}
for (const id of ['bA','bB','bC']) {
  test(`reduced motion: ${id} feedback expires without animation`,()=>{
    const qa=setup(); qa.el(id).onclick();
    assert.notEqual(qa.el('lcdText').textContent,'Bird รอคุณสอน จ. 10.00 น.');
    qa.expire();
    assert.equal(qa.el('lcdText').textContent,'Bird รอคุณสอน จ. 10.00 น.');
    assert.equal(qa.intervals(),0);
    assert.equal(qa.el('taught').textContent,0);
  });
}
test('renaming during feedback updates LCD immediately',()=>{
  const qa=setup();qa.el('bB').onclick();qa.el('nameInput').value='New';qa.el('nameInput').input();
  assert.equal(qa.el('lcdText').textContent,'New รอคุณสอน จ. 10.00 น.');
  qa.expire();assert.equal(qa.el('lcdText').textContent,'New รอคุณสอน จ. 10.00 น.');
});
