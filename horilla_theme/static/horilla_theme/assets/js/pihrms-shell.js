(() => {
    const sidebar = document.getElementById("sidebar");
    const toggle = document.getElementById("piSidebarToggle");
    const closeButton = document.getElementById("piSidebarClose");
    const backdrop = document.getElementById("piSidebarBackdrop");
    const header = document.getElementById("mainHeader");
    const main = document.getElementById("ohMainContent");
    if (!sidebar || !toggle || !closeButton || !backdrop || !header || !main) return;

    const desktop = window.matchMedia("(min-width: 1024px)");
    const focusable = "a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex='-1'])";
    const background = new Set();
    const navigationRequests = new WeakSet();
    let open = false;

    function openDrawer() {
        if (open || desktop.matches) return;

        open = true;
        toggle.setAttribute("aria-expanded", "true");
        sidebar.setAttribute("role", "dialog");
        sidebar.setAttribute("aria-modal", "true");
        sidebar.classList.add("pi-drawer-open");
        document.body.classList.add("pi-drawer-active");
        backdrop.hidden = false;
        closeButton.focus();

        for (const element of document.body.children) {
            if (element === sidebar || element === backdrop || element.inert) continue;
            element.inert = true;
            background.add(element);
        }
    }

    function closeDrawer(destination = toggle) {
        if (!open) return;

        open = false;
        for (const element of background) element.inert = false;
        background.clear();
        document.body.classList.remove("pi-drawer-active");
        sidebar.classList.remove("pi-drawer-open");
        sidebar.removeAttribute("aria-modal");
        sidebar.removeAttribute("role");
        backdrop.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
        destination.focus({ preventScroll: true });
    }

    toggle.addEventListener("click", openDrawer);
    closeButton.addEventListener("click", () => closeDrawer());
    backdrop.addEventListener("click", () => closeDrawer());
    desktop.addEventListener("change", (event) => {
        if (event.matches) closeDrawer(document.getElementById("sidebarPinBtn") || main);
    });
    document.addEventListener("focusin", (event) => {
        if (open && !sidebar.contains(event.target)) closeButton.focus();
    });
    document.addEventListener("keydown", (event) => {
        if (!open) return;
        if (event.key === "Escape") {
            event.preventDefault();
            closeDrawer();
        } else if (event.key === "Tab") {
            const controls = [...sidebar.querySelectorAll(focusable)].filter(
                (element) => element.getClientRects().length && getComputedStyle(element).visibility === "visible",
            );
            const first = controls[0];
            const last = controls[controls.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }
    });

    document.addEventListener("htmx:beforeRequest", (event) => {
        const { elt, target, xhr } = event.detail;
        if (target === main && xhr && sidebar.contains(elt)) navigationRequests.add(xhr);
    });
    document.addEventListener("htmx:afterSettle", (event) => {
        const { target, xhr } = event.detail;
        if (!open || target !== main || !navigationRequests.has(xhr) || xhr.status < 200 || xhr.status >= 300) return;
        closeDrawer(main);
    });

    function syncHeaderHeight() {
        document.body.style.setProperty("--pi-header-height", `${header.offsetHeight}px`);
    }

    syncHeaderHeight();
    if ("ResizeObserver" in window) {
        new ResizeObserver(syncHeaderHeight).observe(header);
    } else {
        window.addEventListener("resize", syncHeaderHeight);
    }
})();
