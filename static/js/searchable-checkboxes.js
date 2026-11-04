(function () {
    function initializePicker(picker) {
        const search = picker.querySelector("[data-checkbox-search]");
        const options = Array.from(picker.querySelectorAll("[data-checkbox-option]"));
        const count = picker.querySelector("[data-selection-count]");
        const noResults = picker.querySelector("[data-no-checkbox-results]");
        const controls = picker.querySelector("[data-checkbox-tools]");
        if (!search || options.length === 0 || !count || !controls) return;

        function update() {
            const query = search.value.trim().toLocaleLowerCase();
            let visibleCount = 0;
            let selectedCount = 0;
            options.forEach(function (option) {
                const checkbox = option.querySelector('input[type="checkbox"]');
                const matches = option.textContent.toLocaleLowerCase().includes(query);
                option.hidden = !matches;
                if (matches) visibleCount += 1;
                if (checkbox && checkbox.checked) selectedCount += 1;
            });
            count.textContent = selectedCount + " selected";
            if (noResults) noResults.hidden = visibleCount > 0;
        }

        search.addEventListener("input", update);
        picker.addEventListener("change", function (event) {
            if (event.target.matches('input[type="checkbox"]')) update();
        });
        const selectVisible = picker.querySelector("[data-select-visible]");
        if (selectVisible) {
            selectVisible.addEventListener("click", function () {
                options.forEach(function (option) {
                    if (option.hidden) return;
                    const checkbox = option.querySelector('input[type="checkbox"]');
                    if (checkbox && !checkbox.checked) {
                        checkbox.checked = true;
                        checkbox.dispatchEvent(new Event("change", { bubbles: true }));
                    }
                });
                update();
            });
        }
        const clearSelection = picker.querySelector("[data-clear-selection]");
        if (clearSelection) {
            clearSelection.addEventListener("click", function () {
                options.forEach(function (option) {
                    const checkbox = option.querySelector('input[type="checkbox"]');
                    if (checkbox && checkbox.checked) {
                        checkbox.checked = false;
                        checkbox.dispatchEvent(new Event("change", { bubbles: true }));
                    }
                });
                update();
            });
        }

        picker.classList.add("is-enhanced");
        update();
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-searchable-checkboxes]").forEach(initializePicker);
    });
})();
