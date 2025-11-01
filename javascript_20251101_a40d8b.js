// ==UserScript==
// @name         AE2I Media Auto-save
// @namespace    http://tampermonkey.net/
// @version      1.1
// @description  Sauvegarde auto après upload média
// @author       You
// @match        *://*/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';
    
    console.log('🔧 Script AE2I Media Auto-save chargé');
    
    // Méthode 1: Surveiller tous les ajouts dans la galerie
    const observer = new MutationObserver((mutations) => {
        for (let mutation of mutations) {
            if (mutation.addedNodes.length > 0) {
                console.log('🔄 Changement détecté dans la galerie');
                triggerAutoSave();
            }
        }
    });
    
    // Méthode 2: Surveiller les inputs file
    function setupFileInputs() {
        document.querySelectorAll('input[type="file"]').forEach(input => {
            input.addEventListener('change', function() {
                console.log('📁 Fichier sélectionné, sauvegarde dans 3s...');
                setTimeout(triggerAutoSave, 3000);
            });
        });
    }
    
    // Méthode 3: Surveiller les clics sur les boutons d'upload
    function setupUploadButtons() {
        document.addEventListener('click', function(e) {
            const target = e.target;
            if (target.textContent.includes('Upload') || 
                target.textContent.includes('Téléverser') ||
                target.textContent.includes('Ajouter') ||
                target.closest('[onclick*="upload"]')) {
                console.log('📤 Bouton upload cliqué, sauvegarde dans 5s...');
                setTimeout(triggerAutoSave, 5000);
            }
        });
    }
    
    function triggerAutoSave() {
        if (window.saveAdminData) {
            console.log('💾 Tentative de sauvegarde...');
            // Essayer différentes clés possibles
            const keys = ['media_library', 'medias', 'gallery', 'media', 'uploads'];
            
            keys.forEach(key => {
                try {
                    window.saveAdminData(key);
                    console.log(`✅ Sauvegarde tentée avec la clé: ${key}`);
                } catch (e) {
                    console.log(`❌ Erreur avec ${key}:`, e);
                }
            });
        } else {
            console.log('❌ saveAdminData non trouvé');
        }
    }
    
    // Démarrer la surveillance
    setTimeout(() => {
        const gallery = document.querySelector('.admin-media-manager, .media-gallery, .upload-area');
        if (gallery) {
            observer.observe(gallery, { childList: true, subtree: true });
            console.log('👀 Surveillance de la galerie activée');
        }
        
        setupFileInputs();
        setupUploadButtons();
        console.log('🔧 Toutes les méthodes activées');
    }, 3000);
    
})();
