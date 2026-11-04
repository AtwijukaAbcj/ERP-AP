(() => {
    const tables = document.querySelectorAll("table:not([data-no-csv-export])");

    const csvCell = (cell) => {
        const control = cell.querySelector("input, select, textarea");
        const value = (control ? control.value : cell.textContent || "").trim();
        const safeValue = /^[=+\-@]/.test(value) ? `'${value}` : value;
        return `"${safeValue.replace(/"/g, '""')}"`;
    };

    const slug = (value) => value
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "") || "table";

    const usedActionToolbars = new WeakSet();
    const toolbarSelectors = ".d-flex, .manage-wrap, .toolbar, [data-table-actions]";
    const findActionToolbar = (element) => {
        let current = element;

        while (current && current !== document.body) {
            let sibling = current.previousElementSibling;
            while (sibling) {
                const toolbar = sibling.matches(".page-header")
                    ? sibling.querySelector(".toolbar")
                    : sibling;
                if (
                    toolbar &&
                    !usedActionToolbars.has(toolbar) &&
                    toolbar.matches(toolbarSelectors) &&
                    !toolbar.querySelector("form") &&
                    toolbar.querySelector("a.btn, button.btn")
                ) {
                    return toolbar;
                }
                if (
                    sibling.matches("a.btn, button.btn") &&
                    !sibling.closest("form")
                ) {
                    const actionToolbar = document.createElement("div");
                    actionToolbar.className = "d-flex flex-wrap align-items-center gap-2 mb-3";
                    sibling.before(actionToolbar);
                    sibling.classList.remove("mb-3");
                    actionToolbar.append(sibling);
                    return actionToolbar;
                }
                sibling = sibling.previousElementSibling;
            }
            current = current.parentElement;
        }

        return null;
    };

    tables.forEach((table, index) => {
        const exportTarget = table.dataset.csvExportTarget
            ? document.querySelector(table.dataset.csvExportTarget)
            : null;
        const insertionPoint = table.closest(".table-responsive") || table;
        const actionToolbar = exportTarget
            ? null
            : findActionToolbar(insertionPoint);
        const container = exportTarget || actionToolbar || insertionPoint.parentElement;
        if (!container) {
            return;
        }

        const button = document.createElement("button");
        button.type = "button";
        button.className = exportTarget || actionToolbar
            ? "btn btn-sm btn-outline-secondary"
            : "btn btn-sm btn-outline-secondary mb-2";
        button.textContent = "Export visible rows (CSV)";
        button.setAttribute("aria-label", `Export table ${index + 1} as CSV`);

        button.addEventListener("click", () => {
            const rows = Array.from(table.rows).map((row) =>
                Array.from(row.cells).map(csvCell).join(",")
            );
            const csv = `\uFEFF${rows.join("\r\n")}`;
            const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            const caption = table.querySelector("caption");
            const tableName = caption ? caption.textContent : `table-${index + 1}`;

            link.href = url;
            link.download = `${slug(document.title)}-${slug(tableName)}.csv`;
            link.click();
            URL.revokeObjectURL(url);
        });

        if (exportTarget || actionToolbar) {
            container.append(button);
            if (actionToolbar) {
                usedActionToolbars.add(actionToolbar);
            }
        } else {
            container.insertBefore(button, insertionPoint);
        }
    });
})();
