// static/js/ui.js
// Shared sidebar behavior: active link + collapsible groups + persistence (no dependencies)
document.addEventListener("DOMContentLoaded", () => {
    // --- Sidebar root (works with class only, no need for id) ---
    const menu = document.querySelector(".sidebar-menu");
    if (!menu) return;

    // --- Normalize current path (avoid trailing slash mismatch) ---
    const currentPath = (window.location.pathname || "").replace(/\/+$/, "");

    /* =========================
       1) Active link marker
       - Marks the current page link as .active
       - Works for both main items and submenu items
    ========================== */
    const links = menu.querySelectorAll("a.menu-item");
    links.forEach((a) => {
        const href = (a.getAttribute("href") || "").replace(/\/+$/, "");
        if (!href) return;

        if (href === currentPath) {
            a.classList.add("active");
        }
    });

    /* =========================
       2) Collapsible groups (generic)
       - Opens group if:
         a) It contains an active link
         b) Or user previously left it open (localStorage)
       - Saves open/close state per group via data-group key
    ========================== */
    const groups = menu.querySelectorAll(".menu-group");
    groups.forEach((group) => {
        const groupKey = group.getAttribute("data-group") || "group";
        const storageKey = `sidebar_group_${groupKey}_open`;

        const btn = group.querySelector('[data-toggle="menu-group"]');
        if (!btn) return;

        // If a submenu link is active, force open
        const hasActiveInside = !!group.querySelector(".menu-sub a.menu-item.active");

        // Otherwise, use persisted state
        const saved = localStorage.getItem(storageKey);
        const shouldOpen = hasActiveInside || saved === "1";

        if (shouldOpen) {
            group.classList.add("is-open");
            btn.setAttribute("aria-expanded", "true");
        } else {
            btn.setAttribute("aria-expanded", "false");
        }

        // Toggle handler + persistence
        btn.addEventListener("click", () => {
            const open = group.classList.toggle("is-open");
            btn.setAttribute("aria-expanded", open ? "true" : "false");
            localStorage.setItem(storageKey, open ? "1" : "0");
        });
    });
});
