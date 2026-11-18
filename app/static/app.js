// Best-effort attempt to open the official Jellyfin iOS app when the user
// taps "Play in Jellyfin" on an iOS device, falling back to the normal web
// link if the app isn't installed (or doesn't respond in time).
//
// There is no official, documented deep link scheme that can jump straight
// to a specific item for an arbitrary self-hosted server (see
// https://github.com/jellyfin/jellyfin-ios/issues/466), so this only opens
// the app to wherever it last was - it's strictly a "switch to the app
// instead of the browser" nicety, not a true per-movie deep link.
(function () {
  var IOS_APP_SCHEME = "org.jellyfin.expo://";
  var FALLBACK_DELAY_MS = 1500;

  function isIOS() {
    return (
      /iPad|iPhone|iPod/.test(navigator.userAgent) ||
      // iPadOS 13+ reports itself as a Mac but still has touch support.
      (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
    );
  }

  function attachAppLaunch(link) {
    link.addEventListener("click", function (event) {
      var webUrl = link.href;
      if (!webUrl || webUrl === "#") return;

      event.preventDefault();

      var fellBack = false;
      var fallbackToWeb = function () {
        if (fellBack) return;
        fellBack = true;
        window.location.href = webUrl;
      };

      // If the tab is hidden shortly after we try the app scheme, assume
      // the app opened and skip the web fallback.
      document.addEventListener(
        "visibilitychange",
        function onVisibilityChange() {
          if (document.hidden) {
            fellBack = true;
          }
        },
        { once: true }
      );

      window.location.href = IOS_APP_SCHEME;
      setTimeout(fallbackToWeb, FALLBACK_DELAY_MS);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!isIOS()) return;
    document.querySelectorAll(".play-button").forEach(attachAppLaunch);
  });
})();
