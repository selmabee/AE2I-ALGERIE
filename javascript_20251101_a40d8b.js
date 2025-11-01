// ==UserScript==
// @name         AE2I Media Auto-save
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Sauvegarde auto après upload média
// @author       You
// @match        *://*/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';
    
    let mediaCount = 0;
    
    setInterval(() => {
        const currentCount = document.querySelectorAll('.media-item').length;
        if (currentCount > mediaCount) {
            mediaCount = currentCount;
            if (window.saveAdminData) {
                setTimeout(() => {
                    window.saveAdminData('media_library');
                    console.log('💾 Média sauvegardé automatiquement');
                }, 1500);
            }
        }
    }, 1000);
})();