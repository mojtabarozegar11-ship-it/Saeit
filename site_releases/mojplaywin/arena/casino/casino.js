"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const overlay = $("age-overlay"), freePlay = $("free-play");
  $("confirm-adult").addEventListener("click", () => {
    overlay.hidden = true;
    freePlay.hidden = false;
    freePlay.scrollIntoView({behavior:"smooth",block:"start"});
    $("roulette-spin").focus({preventScroll:true});
  });
  $("year").textContent=String(new Date().getFullYear());

  // No wagering, credit balance, conversion, rewards or financial outcome exists in this module.
  const supported = Boolean(window.crypto && typeof window.crypto.getRandomValues === "function");
  function randomBelow(n) {
    if (!supported) throw new Error("Secure randomness unavailable; activity disabled.");
    if (!Number.isInteger(n) || n <= 0 || n > 4294967296) throw new RangeError("Invalid range");
    const size = 4294967296, limit = size - (size % n), value = new Uint32Array(1);
    do { window.crypto.getRandomValues(value); } while (value[0] >= limit);
    return value[0] % n;
  }
  const safeAction = (fn, output) => {
    try { fn(); } catch {
      output.textContent = "This device cannot provide secure randomness. Free gameplay is unavailable.";
    }
  };
  if (!supported) {
    $("roulette-result").textContent = "Secure randomness unavailable.";
    $("blackjack-result").textContent = "Secure randomness unavailable.";
    $("reels-result").textContent = "Secure randomness unavailable.";
    $("blackjack-deal").disabled = true;
    $("reels-spin").disabled = true;
  }

  // European-style 0–36 roulette colour practice without bets, odds, tokens or prizes.
  const reds = new Set([1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]);
  let selectedColour = null;
  const colourButtons = [...document.querySelectorAll("[data-colour]")];
  colourButtons.forEach(button => button.addEventListener("click", () => {
    selectedColour=button.dataset.colour;
    colourButtons.forEach(other => other.setAttribute("aria-pressed",String(other===button)));
    $("roulette-detail").textContent = "Selected: " + selectedColour;
    $("roulette-spin").disabled = !supported;
  }));
  $("roulette-spin").addEventListener("click", () => safeAction(() => {
    if (!selectedColour) return;
    const n = randomBelow(37), colour = n===0?"green":reds.has(n)?"red":"black";
    const ball = $("roulette-ball");ball.className="roulette-ball "+colour;ball.textContent=String(n);
    $("roulette-detail").textContent = colour.toUpperCase()+" — European wheel, 0–36";
    $("roulette-result").textContent = selectedColour===colour ?
      "Colour prediction matched. Just a free game outcome." :
      "Colour prediction did not match. No stakes or prizes.";
  },$("roulette-result")));

  // Basic single-deck blackjack practice against dealer 17.
  const suits = ["♠","♥","♣","♦"];
  const faces = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"];
  let deck = [], player = [], dealer = [], roundOpen = false;
  function newDeck() {
    const cards=[]; for(const suit of suits) for(const rank of faces) cards.push({suit,rank});
    for(let i=cards.length-1;i>0;i--){const j=randomBelow(i+1);[cards[i],cards[j]]=[cards[j],cards[i]];}return cards;
  }
  function total(cards) {
    let sum=0, aces=0;
    for(const c of cards) {if(c.rank==="A"){sum+=11;aces++}else if(["J","Q","K"].includes(c.rank)){sum+=10}else{sum+=Number(c.rank)}}
    while(sum>21 && aces>0){sum-=10;aces--}return sum;
  }
  function displayHand(node,cards,hideSecond=false){
    node.replaceChildren();
    cards.forEach((card,i)=>{
      const span=document.createElement("span");
      span.className=""+(["♥","♦"].includes(card.suit)?"red-card":"");
      if(hideSecond&&i===1){span.className="hidden-card";span.textContent="◇";span.setAttribute("aria-label","Hidden dealer card");}
      else{span.textContent=card.rank+card.suit;span.setAttribute("aria-label",card.rank+" of "+({"♠":"spades","♥":"hearts","♣":"clubs","♦":"diamonds"}[card.suit]));}
      node.append(span);
    });
  }
  function renderCards(hideDealer=true){
    displayHand($("dealer-cards"),dealer,hideDealer);
    displayHand($("player-cards"),player);
    $("blackjack-total").textContent="Your total: "+total(player)+(hideDealer?" · Dealer shows "+(dealer[0]?.rank||"—"):" · Dealer total: "+total(dealer));
  }
  function stopRound(label) {
    roundOpen=false;
    $("blackjack-hit").disabled=true;
    $("blackjack-stand").disabled=true;
    $("blackjack-deal").disabled=false;
    renderCards(false);
    $("blackjack-result").textContent=label+" (practice outcome; no money or prize).";
  }
  function dealRound() {
    deck=newDeck();player=[deck.pop(),deck.pop()];dealer=[deck.pop(),deck.pop()];roundOpen=true;
    $("blackjack-deal").disabled=true;
    $("blackjack-hit").disabled=false;
    $("blackjack-stand").disabled=false;
    $("blackjack-result").textContent="Choose Hit or Stand";
    renderCards(true);
    if(total(player)===21 || total(dealer)===21) standRound();
  }
  function hitRound(){
    if(!roundOpen) return;
    player.push(deck.pop());renderCards(true);
    if(total(player)>21)stopRound("Bust — dealer result");
    else if(total(player)===21)standRound();
  }
  function standRound() {
    if(!roundOpen)return;
    while(total(dealer)<17)dealer.push(deck.pop());
    const p=total(player),d=total(dealer);
    const result=p>21?"Bust — dealer result":d>21?"Dealer bust — player result":p>d?"Player result wins":p<d?"Dealer result wins":"Draw";
    stopRound(result);
  }
  $("blackjack-deal").addEventListener("click",()=>safeAction(dealRound,$("blackjack-result")));
  $("blackjack-hit").addEventListener("click",()=>safeAction(hitRound,$("blackjack-result")));
  $("blackjack-stand").addEventListener("click",()=>safeAction(standRound,$("blackjack-result")));

  // Non-monetary visual symbols; matching patterns have zero redeemable value.
  const symbols=["✦","◆","☾","♠","✺","★"];
  $("reels-spin").addEventListener("click",()=>safeAction(()=>{
    const button=$("reels-spin");button.disabled=true;
    const a=randomBelow(symbols.length),b=randomBelow(symbols.length),c=randomBelow(symbols.length);
    $("reel-1").textContent=symbols[a];$("reel-2").textContent=symbols[b];$("reel-3").textContent=symbols[c];
    $("reels-result").textContent=(a===b&&b===c)?"Triple symbol match — visual pattern only.":((a===b||a===c||b===c)?"Two matching symbols — visual pattern only.":"Three different symbols — visual pattern only.");
    button.disabled=false;
  },$("reels-result")));
})();
