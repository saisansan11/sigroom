const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const source = readFileSync('static/js/lodging_cassette_pass.js', 'utf8');

function setup() {
  function element() {
    const listeners = {};
    return {listeners, style: {setProperty() {}}, classList: {add() {}, remove() {}, toggle() {}},
      attrs: {}, setAttribute(k,v) { this.attrs[k]=v; }, focus() {},
      addEventListener(k,v) { listeners[k]=v; },
      fire(type, data={}) { listeners[type]?.({type,button:0,isPrimary:true,pointerId:1,clientX:0,clientY:0,...data}); }};
  }
  const card=element(), cassette=element(), packs=[element(),element()], hubs=[element(),element()];
  card.dataset={nightsTotal:'4',nightsElapsed:'2'};
  card.querySelector=()=>cassette;
  card.querySelectorAll=s=>s.includes('pack')?packs:hubs;
  const ids={keycard:card,cassetteFlipBtn:element(),cassetteQrOpenBtn:element(),cassetteQrDialog:element(),cassetteQrCloseBtn:element()};
  ids.cassetteQrDialog.showModal=()=>{};
  let observer, next=0;
  const pending=new Map();
  const window={matchMedia:()=>({matches:false,addEventListener(){}}),
    requestAnimationFrame:f=>{pending.set(++next,f);return next;}, cancelAnimationFrame:id=>pending.delete(id),setTimeout(){}};
  function IntersectionObserver(f){observer=f;this.observe=()=>{};}
  window.IntersectionObserver=IntersectionObserver;
  vm.runInNewContext(source,{window,IntersectionObserver,document:{hidden:false,getElementById:id=>ids[id],addEventListener(){}}});
  return {card,cassette,ids,pending,visibility:visible=>observer([{isIntersecting:visible}])};
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
