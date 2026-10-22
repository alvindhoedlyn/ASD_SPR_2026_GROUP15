document.addEventListener("DOMContentLoaded", function () {
    const dateInput = document.getElementById("expense_date");
    if (!dateInput || typeof flatpickr === "undefined") return;

    flatpickr(dateInput, {
        locale: "default",
        dateFormat: "Y-m-d",
        allowInput: false,
        disableMobile: true,
        monthSelectorType: "dropdown"
    });
});
