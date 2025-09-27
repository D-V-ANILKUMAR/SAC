document.addEventListener("DOMContentLoaded", function () {
  const menuToggle = document.querySelector(".menu-toggle");
  const sidebar = document.querySelector(".sidebar");

  if (menuToggle && sidebar) {
    menuToggle.addEventListener("click", function () {
      sidebar.classList.toggle("active");
      menuToggle.classList.toggle("active");
    });

    // Close menu when clicking outside
    document.addEventListener("click", function (event) {
      const isClickInside =
        sidebar.contains(event.target) || menuToggle.contains(event.target);

      if (!isClickInside && sidebar.classList.contains("active")) {
        sidebar.classList.remove("active");
        menuToggle.classList.remove("active");
      }
    });
  }
});
