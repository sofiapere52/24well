"use strict";
// The server observes this connection closing, even if unload notifications
// cannot be delivered. Server-sent traffic needs no background-tab JS timer.
let browserSession;
function connectBrowserSession() {
  if (!browserSession) browserSession = new EventSource('/api/browser-session');
}
window.addEventListener('pagehide', () => {
  browserSession?.close();
  browserSession = null;
});
window.addEventListener('pageshow', connectBrowserSession);
connectBrowserSession();
