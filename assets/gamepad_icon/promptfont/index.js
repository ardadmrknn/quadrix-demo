let notice = null;
      
let clearNotice = ()=>{
    if(notice){
        clearTimeout(notice.timeout);
        document.body.removeChild(notice.element);
        notice = null;
    }
}
      
let showNotice = (html)=>{
    clearNotice();
    notice = {};
    notice.element = document.createElement("div");
    notice.element.setAttribute("class", "notice");
    notice.element.innerHTML = html;
    document.body.appendChild(notice.element);
    notice.timeout = setTimeout(clearNotice, 2000);
};

let copyToClipboard = (string)=>{
    navigator.clipboard.writeText(string).then(
        ()=>showNotice("<i>"+string+"</i> copied to clipboard!"),
        ()=>showNotice("Failed to copy to clipboard."));
};

let match = (query, el)=>{
    query = query.trim().toLowerCase();
    if(query === "") return true;
    let inner = el.innerText.toLowerCase();
    for(let k in el.dataset){
        inner += " "+k+":"+el.dataset[k].toLowerCase();
    }
    for(let part of query.split(/ +/)){
        if(!inner.includes(part))
            return false;
    }
    return true;
};

let find = (query)=>{
    for(let glyph of document.querySelectorAll(".glyph")){
        if(match(query, glyph)) return glyph;
    };
    return null;
};

let composer = document.querySelector(".composer");
composer.compose = (glyph)=>{
    composer.value += glyph.dataset["character"];
};

let popup = document.querySelector("#popup");
popup.glyph = null;
popup.addEventListener("click", ()=>popup.classList.add("hidden"));
popup.querySelector(".box").addEventListener("click", (ev)=>ev.stopPropagation());
let hidePopup = ()=>popup.classList.add("hidden");
let showPopup = (glyph)=>{
    popup.glyph = glyph;
    for(let el of popup.querySelectorAll("[data-text]"))
        el.innerText = glyph.dataset[el.dataset.text];
    popup.classList.remove("hidden");
};
for(let el of popup.querySelectorAll(".copy")){
    el.addEventListener("click", ()=>{
        copyToClipboard(el.innerText);
    });
}
for(let el of popup.querySelectorAll(".compose")){
    el.addEventListener("click", ()=>{
        composer.compose(popup.glyph);
        hidePopup();
    });
}
for(let el of document.querySelectorAll(".glyph")){
    el.addEventListener("click", (ev)=>{
        if(ev.ctrlKey) composer.compose(el);
        else showPopup(el)
    });
}

let search = document.querySelector("input[type=search]");
search.addEventListener("input", (ev)=>{
    let query = search.value;
    for(let glyph of document.querySelectorAll(".glyph")){
        if(match(query, glyph))
            glyph.classList.remove("hidden");
        else
            glyph.classList.add("hidden");
    }
    for(let section of document.querySelectorAll(".glyphsection")){
        if(section.querySelector(".glyph:not(.hidden)") !== null)
            section.classList.remove("hidden");
        else
            section.classList.add("hidden");
    }
});

// Try the editor
editor(composer);

// Query parameter wrangling
search.value = new URLSearchParams(document.location.search).get("q");
if(search.value) search.dispatchEvent(new Event('input', {bubbles: true}));

let pre = new URLSearchParams(document.location.search).get("c");
if(pre){
    for(let query of pre.split(' ')){
        let found = find(query);
        if(found) composer.compose(found);
    }
}
      
let updateQuery = ()=>{
    const url = new URL(window.location.href);
    if(search.value)
        url.searchParams.set("q", search.value);
    else
        url.searchParams.delete("q");
    if(composer.value){
        let parts = [];
        for(const codepoint of composer.value){
            let hex = codepoint.codePointAt(0).toString(16); 
            parts.push("0000".substring(0, 4-hex.length)+hex);
        }
        url.searchParams.set("c", parts.join(" "));
    }else
        url.searchParams.delete("c");
    window.history.replaceState(null, '', url);
}
search.addEventListener("change", updateQuery);
composer.addEventListener("change", updateQuery);
