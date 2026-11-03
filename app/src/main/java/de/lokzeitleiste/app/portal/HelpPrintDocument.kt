package de.lokzeitleiste.app.portal

/** Only static help text enters this document; no portal page or personal fields. */
object HelpPrintDocument {
    fun render(title:String,text:String):String {
        require(title.isNotBlank() && title.length<=200 && text.isNotBlank() && text.length<=100000) { "Ungültige Druckanleitung." }
        fun escape(value:String)=value.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\"","&quot;").replace("'","&#39;")
        return "<!doctype html><html lang=\"de\"><head><meta charset=\"utf-8\"><title>${escape(title)}</title><style>@page{size:A4;margin:16mm}body{font:14px/1.6 sans-serif;color:#000;background:#fff}h1{font-size:24px}div{white-space:pre-wrap;overflow-wrap:anywhere}</style></head><body><h1>${escape(title)}</h1><div>${escape(text)}</div></body></html>"
    }
}
