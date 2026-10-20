import mermaid from "./mermaid/mermaid.esm.min.mjs";
// Local, pinned build assets only. Authored docs, not agent messages or user HTML.
mermaid.initialize({startOnLoad:false,securityLevel:"strict",theme:"neutral",maxTextSize:100000,
  fontFamily:"system-ui, sans-serif",flowchart:{htmlLabels:false,useMaxWidth:false}});
window.docsDiagrams = {ready:false, errors:[]};
for (const [i,node] of [...document.querySelectorAll(".diagram-src")].entries()) {
  const source = node.textContent;
  const details=document.createElement("details"),summary=document.createElement("summary"),pre=document.createElement("pre");
  summary.textContent="Текст схемы / доступная альтернатива"; pre.textContent=source;
  details.append(summary,pre);
  const frame=document.createElement("div");frame.className="diagram-frame";
  frame.tabIndex=0;frame.setAttribute("role","region");frame.setAttribute("aria-label",`Схема ${i+1}: прокручиваемая область`);
  node.replaceWith(frame);frame.append(node);frame.after(details);
  node.textContent=source;
  try {
    await mermaid.run({nodes:[node],suppressErrors:false});
    const svg=node.querySelector("svg"), box=svg.viewBox.baseVal;
    const w=box.width,h=box.height;
    if (!(w>0 && h>0)) throw new Error("invalid dimensions");
    const tools=document.createElement("div");tools.className="diagram-tools";
    const output=document.createElement("output");output.setAttribute("aria-live","polite");
    let scale=1;
    function resize(next) {
      scale=Math.max(.03,Math.min(2,next));
      svg.style.width=`${Math.ceil(w*scale)}px`;svg.style.height=`${Math.ceil(h*scale)}px`;
      svg.setAttribute("width",Math.ceil(w*scale));svg.setAttribute("height",Math.ceil(h*scale));
      output.textContent=`${Math.round(scale*100)}%`;
    }
    function add(label,action,key) {
      const b=document.createElement("button");b.type="button";b.textContent=label;
      b.dataset.diagramScale=key;b.addEventListener("click",action);tools.append(b);
    }
    add("Вместить",()=>resize(Math.min(1,(frame.clientWidth-36)/w)),"fit");
    add("100%",()=>{
      resize(1);
      if(source.trim().startsWith("mindmap")) {
        frame.scrollLeft=Math.max(0,(w-frame.clientWidth)/2);
        frame.scrollTop=Math.max(0,(h-frame.clientHeight)/2);
      }
    },"actual");
    add("−",()=>resize(scale/1.25),"out");add("+",()=>resize(scale*1.25),"in");
    tools.append(output);frame.before(tools);
    resize(Math.min(1,(frame.clientWidth-36)/w));
  }
  catch (_) { window.docsDiagrams.errors.push(i);node.textContent="Не удалось отобразить схему. Исходный текст доступен ниже."; }
}
window.docsDiagrams.ready=true;
