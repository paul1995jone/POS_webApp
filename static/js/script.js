        function showSection(sectionId) {
            // Hide all sections
            document.querySelectorAll('.billing-section, .stock-section, .statistics-section, .export-section, .manage-user-section, .items-section, .sales-section, .view-sales-section, .manage-item, .export-data').forEach(section => {
                section.style.display = 'none';
            });
            // Show the selected section
            const activeSection = document.getElementById(sectionId);
            if (activeSection) {
                activeSection.style.display = 'flex';
            }
            // Remove all highlights
            document.querySelectorAll('.sidebar nav button').forEach(btn => btn.classList.remove('active'));
            // Highlight the correct button (whether inside a form or not)
            const formWithTarget = document.querySelector(`.sidebar nav form[data-target="${sectionId}"]`);
            if (formWithTarget) {
                const button = formWithTarget.querySelector('button');
                if (button) button.classList.add('active');
            } else {
                const button = document.querySelector(`.sidebar nav button[data-target="${sectionId}"]`);
                if (button) button.classList.add('active');
            }
            // Update URL (without reload)
            const newUrl = `${window.location.pathname}?section=${sectionId}`;
            history.replaceState(null, '', newUrl);
        }


        let currentFilter = "all";
        function filterItems(type) {
            currentFilter = type;
            const boxes = document.querySelectorAll(".item-box");
            boxes.forEach(box => {
                const btn = box.querySelector(".item-button");
                const isVeg = btn.classList.contains("veg");
                box.style.display = (type === "all") ||
                    (type === "veg" && isVeg) ||
                    (type === "non-veg" && !isVeg) ? "flex" : "none";
            });
        }

        function searchItems() {
            const input = document.getElementById("searchBox").value.toLowerCase();
            const items = document.querySelectorAll(".item-button");
            items.forEach(btn => {
                const name = btn.innerText.toLowerCase();
                const isVeg = btn.classList.contains("veg");
                const visible = (currentFilter === "all") ||
                    (currentFilter === "veg" && isVeg) ||
                    (currentFilter === "non-veg" && !isVeg);
                btn.parentElement.style.display = (name.includes(input) && visible) ? "flex" : "none";
            });
        }

        function submitSelected(className, formId) {
            const checkboxes = document.querySelectorAll(`.${className}`);
            let hasSelection = false;
            checkboxes.forEach(cb => {
                if (cb.checked) hasSelection = true;
            });

            if (!hasSelection) {
                alert("Please select at least one item.");
                return;
            }

            document.getElementById(formId).submit();
        }

        function renderLineChart(chartData) {
            const ctx = document.getElementById('lineChart').getContext('2d');

            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: chartData.labels,
                    datasets: chartData.datasets
                },
                options: {
                    responsive: true,
                    interaction: { mode: 'index', intersect: false },
                    stacked: false,
                    plugins: {
                        title: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Quantity' }
                        },
                        x: {
                            title: { display: true, text: 'Date' }
                        }
                    }
                }
            });
        }

        function renderSalesBarChart(data) {
            const ctx = document.getElementById('salesBarChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: data.datasets
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { position: 'top' },
                        title: { display: true, text: 'Total Sales (₹) per Day' }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Total ₹' }
                        },
                        x: {
                            title: { display: true, text: 'Date' }
                        }
                    }
                }
            });
        }

        function selectItem(element) {
            const itemId = element.getAttribute("data-id");
            const name = element.getAttribute("data-name");
            const price = element.getAttribute("data-price");
            const veg = element.getAttribute("data-veg") === "true";
            const available = element.getAttribute("data-available") === "true";

            // Highlight selection
            document.querySelectorAll('.item-row').forEach(el => el.classList.remove('selected'));
            element.classList.add('selected');

            // Fill the edit form fields
            document.getElementById("edit-item-id").value = itemId;
            document.getElementById("edit-item-name").value = name;
            document.getElementById("edit-item-price").value = price;
            document.getElementById("edit-item-veg").checked = veg;
            document.getElementById("edit-item-available").checked = available;

            // Dynamically set form actions
            document.getElementById("editItemForm").action = `/update_item/${itemId}`;
            document.getElementById("delete-item-id").value = itemId;
            document.getElementById("deleteItemForm").action = `/delete_item/${itemId}`;
            document.getElementById("delete-btn").disabled = false;
        }

        function selectDeletedItem(element) {
            const itemId = element.getAttribute("data-id");

            // Highlight selection
            document.querySelectorAll('.deleted-item-row').forEach(el => el.classList.remove('selected'));
            element.classList.add('selected');

            // Set ID in restore form and enable button
            document.getElementById("restore-item-id").value = itemId;
            document.getElementById("restoreItemForm").action = `/restore_item/${itemId}`;
            document.getElementById("restore-btn").disabled = false;
        }

        document.addEventListener("DOMContentLoaded", function () {
            const params = new URLSearchParams(window.location.search);
            let section = params.get("section");

            // Use Flask-injected value if no query param
            if (!section && typeof initialSection !== 'undefined') {
                section = initialSection;
            }

            // If you're in admin dashboard, default section should be 'manage_users'
            const isAdmin = window.location.pathname.includes('/admin');
            section = section || (isAdmin ? 'manage_users' : 'billing');
            showSection(section);

            // Too show error msg in duplicate add items.
            if (params.get('error') === 'exists') {
                        alert("Item already exists! you can update it.");
                    }
            if (window.chartData) {
                renderLineChart(window.chartData);
            }
            if (window.salesBarData) {
                renderSalesBarChart(window.salesBarData);
            }
        });


