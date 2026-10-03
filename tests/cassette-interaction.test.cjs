const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const source = readFileSync('static/js/lodging_cassette_pass.js', 'utf8');

function setup({legacyDialog=false}={}) {
  function element() {
    const listeners = {};
    return {listeners, style: {setProperty() {}}, classList: {add() {}, remove() {}, toggle() {}},
      removeAttribute(k) { delete this.attrs[k]; }, attrs: {}, setAttribute(k,v) { this.attrs[k]=v; }, focus() {},
      addEventListener(k,v) { listeners[k]=v; },
      fire(type, data={}) { listeners[type]?.({type,button:0,isPrimary:true,pointerId:1,clientX:0,clientY:0,...data}); }};
  }
  const card=element(), cassette=element(), packs=[element(),element()], hubs=[element(),element()];
  card.dataset={nightsTotal:'4',nightsElapsed:'2'};
  card.querySelector=()=>cassette;
  card.querySelectorAll=s=>s.includes('pack')?packs:hubs;
  const ids={keycard:card,cassetteFlipBtn:element(),cassetteQrOpenBtn:element(),cassetteQrDialog:element(),cassetteQrCloseBtn:element()};
  if (!legacyDialog) ids.cassetteQrDialog.showModal=()=>{};
  let observer, next=0;
  const pending=new Map();
  const window={matchMedia:()=>({matches:false,addEventListener(){}}),
    requestAnimationFrame:f=>{pending.set(++next,f);return next;}, cancelAnimationFrame:id=>pending.delete(id),setTimeout(){}};
  function IntersectionObserver(f){observer=f;this.observe=()=>{};}
  window.IntersectionObserver=IntersectionObserver;
  vm.runInNewContext(source,{window,IntersectionObserver,document:{hidden:false,getElementById:id=>ids[id],addEventListener(){}}});
  return {card,cassette,ids,pending,packs,frame(now) { const callbacks=[...pending.values()]; pending.clear(); callbacks.forEach(f=>f(now)); },visibility:visible=>observer([{isIntersecting:visible}])};
}
test('cancelled touch does not flip; intentional tap does',()=>{
  const {card}=setup();
  card.fire('pointerdown');card.fire('pointercancel');
  assert.equal(card.attrs['aria-pressed'],'false');
  card.fire('pointerdown');card.fire('pointerup');
  assert.equal(card.attrs['aria-pressed'],'true');
});
test('drag returns to rest without flip and QR side cannot tilt',()=>{
  const {card,cassette,ids}=setup();
  card.fire('pointerdown');card.fire('pointermove',{clientX:80});
  assert.match(cassette.style.transform,/rotateY\(20.00deg\)/);
  card.fire('pointerup');assert.equal(card.attrs['aria-pressed'],'false');
  ids.cassetteFlipBtn.fire('click');
  card.fire('pointerdown');card.fire('pointermove',{clientX:80});
  assert.match(cassette.style.transform,/rotateY\(180.00deg\)/);
});
test('reels run only on visible front with QR dialog closed',()=>{
  const {ids,pending,visibility}=setup();
  assert.equal(pending.size,0);visibility(true);assert.equal(pending.size,1);
  ids.cassetteQrOpenBtn.fire('click');assert.equal(pending.size,0);
  ids.cassetteQrDialog.fire('close');assert.equal(pending.size,1);
  visibility(false);assert.equal(pending.size,0);
});

for (const pause of ['viewport', 'dialog']) {
  test(`winding resumes without jumping after ${pause} pause`,()=>{
    const qa=setup(); qa.visibility(true); qa.frame(100); qa.frame(150);
    const before=qa.packs[1].attrs.transform;
    if(pause==='viewport') { qa.visibility(false); qa.visibility(true); }
    else { qa.ids.cassetteQrOpenBtn.fire('click'); qa.ids.cassetteQrDialog.fire('close'); }
    qa.frame(10000);
    assert.equal(qa.packs[1].attrs.transform,before);
    qa.frame(10050);
    assert.notEqual(qa.packs[1].attrs.transform,before);
  });
}
test('legacy QR close hides dialog and resumes reels',()=>{
  const {ids,pending,visibility}=setup({legacyDialog:true}); visibility(true);
  ids.cassetteQrOpenBtn.fire('click'); assert.equal(pending.size,0);
  assert.equal(ids.cassetteQrDialog.attrs.open,'');
  ids.cassetteQrCloseBtn.fire('click');
  assert.equal(ids.cassetteQrDialog.attrs.open,undefined);
  assert.equal(pending.size,1);
});
