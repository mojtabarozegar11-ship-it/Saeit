import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const cake=readFileSync(new URL('../../../templates/taniya_studio/index.html',import.meta.url),'utf8');
const echo=readFileSync(new URL('../../echoform/signal-lattice-r38.html',import.meta.url),'utf8');
test('Cake Maker supports undo without erasing frosting or topping',()=>{
  assert.match(cake,/data-cake-action="undo"/);
  assert.match(cake,/candles===0\?'disabled'/);
  assert.match(cake,/candles=Math\.max\(0,candles-1\);draw\(\)/);
  assert.match(cake,/let icing='#ff79b8',topping='🍓',candles=0/);
});
test('ECHOFORM playback announces step number separately from tile number',()=>{
  assert.match(echo,/for\(const \[index,i\] of sequence\.entries\(\)\)/);
  assert.match(echo,/light\(i,'active',index\+1\)/);
  assert.match(echo,/Observe step '\+step\+' of '\+sequence\.length\+' \(tile '/);
});
