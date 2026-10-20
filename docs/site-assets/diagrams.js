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
  try { await mermaid.run({nodes:[node],suppressErrors:false}); }
  catch (_) { window.docsDiagrams.errors.push(i);node.textContent="Не удалось отобразить схему. Исходный текст доступен ниже."; }
}
window.docsDiagrams.ready=true;
