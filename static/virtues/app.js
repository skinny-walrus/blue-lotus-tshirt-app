const virtues={
metta:{name:'Loving-kindness',print:'Loving\nkindness',pali:'Mettā',meaning:'An inclusive wish for the well-being of ourselves and others, offered without asking for anything in return.',practice:'Pause before your next conversation. Silently wish the other person well, then listen with care.',phrase:'May all beings be well.'},
karuna:{name:'Compassion',print:'Compassion',pali:'Karuṇā',meaning:'A caring response to suffering, with the wish to ease it. Compassion turns our attention toward someone who needs support.',practice:'Notice one person having a difficult day. Ask what would help, and offer something you can give.',phrase:'Let care become action.'},
mudita:{name:'Appreciative joy',print:'Appreciative\njoy',pali:'Muditā',meaning:'Taking genuine delight in the happiness and good fortune of others, without making their success a comparison with our own.',practice:'Celebrate someone’s good news today. Give them your full attention and let their happiness be enough.',phrase:'Make room for another’s joy.'},
upekkha:{name:'Equanimity',print:'Equanimity',pali:'Upekkhā',meaning:'An even, caring mind amid life’s changes. Equanimity supports compassion without becoming indifference.',practice:'When something unsettles you, take three breaths. Choose a thoughtful response to what you can influence.',phrase:'Meet change with a steady heart.'}
};
const colors={Gray:{hex:'#92928f',front:'garment-gray-front.jpg',back:'garment-gray-back.jpg'},'Mystic Blue':{hex:'#6486bd',front:'garment-mystic-blue-front.jpg',back:'garment-mystic-blue-back.jpg'},'Ice Blue':{hex:'#7c9da6',front:'garment-gray-front.jpg',back:'garment-gray-back.jpg'},Moss:{hex:'#73765f',image:'garment-moss.png'},Bay:{hex:'#b8bfab',image:'garment-bay.png'},Ivory:{hex:'#e6dcc7',image:'garment-ivory.png'}};
const sizes=['S','M','L','XL','2XL'];
const products={metta:{name:'Mettā Loving-kindness',file:'metta-loving-kindness.png'},karuna:{name:'Karuṇā Compassion',file:'karuna-softer-heart.png'},karuna_crane:{name:'Karuṇā Compassion · Crane',file:'compassion-crane.png'},mudita:{name:'Muditā Joy',file:'mudita-joy.png'},upekkha:{name:'Upekkhā Equanimity',file:'upekkha-equanimity.png'},upekkha_koi:{name:'Upekkhā Equanimity – Koi',file:'upekkha-equanimity-koi.png'}};
const selections={...virtues,upekkha_koi:{...virtues.upekkha,name:'Equanimity – Koi'},karuna_crane:{...virtues.karuna,name:'Compassion · Crane'}};
let state={virtue:'metta',color:'Gray',size:'M',side:'back'};
const $=id=>document.getElementById(id);
const artwork=document.createElement('img');artwork.id='mettaArt';artwork.className='metta-art';artwork.src='/static/metta-loving-kindness.png';artwork.alt='Mettā Loving Kindness artwork with Buddha, lotus, landscape and blessing';$('shirt').append(artwork);
const money=n=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(n/100);
let cart=[];try{const saved=JSON.parse(localStorage.getItem('blueLotusCart')||'[]');if(Array.isArray(saved))cart=saved.filter(x=>x&&typeof x.breed==='string'&&Object.hasOwn(colors,x.color)&&sizes.includes(x.size)&&Number.isInteger(x.quantity)&&x.quantity>=1&&x.quantity<=10)}catch{}
function quantity(){return Number($('quantity').value)}
function priceFor(size){return size==='2XL'?3295:2995}
function update(){
 const v=selections[state.virtue],c=colors[state.color],front=state.side==='front';
 $('virtue').value=state.virtue;$('productName').textContent=v.name+' Tee';$('previewTitle').textContent=v.name+' · '+state.color;
 $('meaning').textContent=v.meaning;$('practice').textContent=v.practice;$('pali').textContent=v.pali+' / '+v.name;
 $('printName').textContent=v.print;$('printName').style.whiteSpace='pre-line';$('printPali').textContent=v.pali;$('printPhrase').textContent=v.phrase;
 $('shirt').className='shirt '+state.side;
 $('garment').src='/static/garment-ivory.png';$('garment').alt=state.color+' shirt '+state.side;
 // Keep the Ivory silhouette and folds for every color; tint only the garment layer.
 const channels=c.hex.slice(1).match(/../g).map(h=>parseInt(h,16)/220);
 $('garmentTintMatrix').setAttribute('values',channels.flatMap(v=>[.2126*v,.7152*v,.0722*v,0,0]).concat([0,0,0,1,0]).join(' '));
 $('garment').style.filter=state.color==='Ivory'?'none':'url(#garmentTint)';
 const product=products[state.virtue];
 if(product){artwork.src='/static/previews/'+product.file.replace(/\.png$/,'.webp');artwork.alt=product.name+' artwork and blessing'}
 $('chestLogo').hidden=!front;$('printArea').hidden=front||Boolean(product);artwork.hidden=front||!product;$('placement').textContent=front?'Front · Blue logo on wearer’s left chest':product?'Back · '+v.pali+' artwork':'Back · Planned virtue artwork placement';
 $('frontButton').setAttribute('aria-pressed',String(front));$('backButton').setAttribute('aria-pressed',String(!front));
 $('price').textContent=state.size==='2XL'?'$32.95':'$29.95';
 const available=Boolean(product),valid=$('quantity').checkValidity();$('addButton').disabled=!available||!valid;$('addButton').textContent=available?'Add to cart · '+money(priceFor(state.size)*(valid?quantity():1)):'Artwork coming soon';$('availability').textContent=available?'Shipping and tax will be confirmed by email. No payment is collected here.':'This virtue’s artwork is still in development.';
 document.querySelectorAll('[data-color]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.color===state.color)));
 document.querySelectorAll('[data-size]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.size===state.size)));
}
for(const name of ['Gray','Mystic Blue','Ice Blue','Moss','Ivory','Bay']){const c=colors[name],b=document.createElement('button');b.type='button';b.dataset.color=name;b.title=name;b.setAttribute('aria-label',name);const swatch=document.createElement('i');swatch.style.background=c.hex;swatch.setAttribute('aria-hidden','true');const label=document.createElement('small');label.textContent=name;b.append(swatch,label);b.onclick=()=>{state.color=name;update()};$('colors').append(b)}
for(const size of sizes){const b=document.createElement('button');b.type='button';b.dataset.size=size;b.textContent=size;b.onclick=()=>{state.size=size;update()};$('sizes').append(b)}
Object.entries(virtues).forEach(([key,v],i)=>{const card=document.createElement('article');card.className='virtue-card';card.innerHTML=`<span class="virtue-number">0${i+1}</span><h3>${v.name}</h3><span class="pali">${v.pali}</span><p>${v.meaning}</p><button type="button">Explore ${v.name.toLowerCase()} ↗</button>`;card.querySelector('button').onclick=()=>{state.virtue=key;state.side='back';update();$('virtue').focus({preventScroll:true});document.querySelector('.product').scrollIntoView({block:'start'})};$('virtueCards').append(card)});
 $('virtue').onchange=e=>{state.virtue=e.target.value;update()};$('frontButton').onclick=()=>{state.side='front';update()};$('backButton').onclick=()=>{state.side='back';update()};$('quantity').oninput=update;
for(const [id,step] of [['quantityDown',-1],['quantityUp',1]])$(id).onclick=()=>{const current=quantity();$('quantity').value=Math.max(1,Math.min(10,(Number.isFinite(current)?current:1)+step));update()};update();
function saveCart(){try{localStorage.setItem('blueLotusCart',JSON.stringify(cart));return true}catch{$('cartMessage').textContent='Your browser could not save the cart. Please allow local storage and try again.';return false}}
function renderCart(){
 $('cartCount').textContent=cart.reduce((n,x)=>n+x.quantity,0);$('cartItems').replaceChildren();
 if(!cart.length)$('cartItems').textContent='Your cart is empty. Choose a shirt to begin.';
 cart.forEach((item,index)=>{const row=document.createElement('article');row.className='cart-item';const detail=document.createElement('div'),name=document.createElement('strong'),info=document.createElement('p');name.textContent=item.breed+' Tee';info.textContent=item.color+' · '+item.size+' · Qty '+item.quantity+' · '+money(priceFor(item.size)*item.quantity);detail.append(name,info);const remove=document.createElement('button');remove.type='button';remove.textContent='Remove';remove.setAttribute('aria-label','Remove '+item.breed+' '+item.color+' '+item.size);remove.onclick=()=>{cart.splice(index,1);saveCart();renderCart()};row.append(detail,remove);$('cartItems').append(row)});
 $('subtotal').textContent=money(cart.reduce((n,x)=>n+priceFor(x.size)*x.quantity,0));$('checkoutButton').disabled=!cart.length;
}
$('addButton').onclick=()=>{
 if(!products[state.virtue]||!$('quantity').reportValidity())return;
 const item={breed:products[state.virtue].name,color:state.color,size:state.size,quantity:quantity(),unit_price_cents:priceFor(state.size)};
 const same=cart.find(x=>x.breed===item.breed&&x.color===item.color&&x.size===item.size);
 if(same&&same.quantity+item.quantity>10){$('cartMessage').textContent='You can add up to 10 of the same shirt. Adjust the quantity in your cart first.';return}
 if(!same&&cart.length>=20){$('cartMessage').textContent='Your cart can contain up to 20 selections.';return}
 const previous=JSON.stringify(cart);if(same)same.quantity+=item.quantity;else cart.push(item);
 if(!saveCart()){cart=JSON.parse(previous);return}renderCart();$('cartMessage').textContent='Added to your cart.';$('cartDialog').showModal();
};
$('cartOpen').onclick=()=>{renderCart();$('cartDialog').showModal()};$('cartClose').onclick=()=>$('cartDialog').close();$('checkoutButton').onclick=()=>{if(cart.length&&saveCart())location.href='/checkout'};renderCart();
if(document.modelContext?.registerTool){try{Promise.resolve(document.modelContext.registerTool({name:'configure_virtue_preview',description:'Change the virtue shirt preview. Does not place or submit an order.',inputSchema:{type:'object',properties:{virtue:{type:'string',enum:Object.keys(selections)},color:{type:'string',enum:Object.keys(colors)},size:{type:'string',enum:sizes},side:{type:'string',enum:['front','back']}},additionalProperties:false},annotations:{readOnlyHint:false,untrustedContentHint:false},execute(input){if(!input||typeof input!=='object'||Array.isArray(input))throw Error('Invalid configuration');for(const [k,v] of Object.entries(input)){const allowed={virtue:Object.keys(selections),color:Object.keys(colors),size:sizes,side:['front','back']}[k];if(!allowed?.includes(v))throw Error('Invalid '+k)}state={...state,...input};update();return {...state,orderSubmitted:false}}})).catch(()=>{})}catch{}}
