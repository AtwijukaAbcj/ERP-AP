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

    tables.forEach((table, index) => {
        const insertionPoint = table.closest(".table-responsive") || table;
        const container = insertionPoint.parentElement;
        if (!container) {
            return;
        }

        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-sm btn-outline-secondary mb-2";
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

        container.insertBefore(button, insertionPoint);
    });
})();
