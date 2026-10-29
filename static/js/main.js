"use strict";

// side navigation bar
function toggleSidebar() {
  const sidebar = document.getElementById("side-nav");
  const main = document.getElementById("main");
  const navbar = document.getElementById("top-navbar");
  const manageWrap = document.querySelector(".manage-wrap");

  if (!sidebar || !main || !navbar) {
    console.error("Unable to toggle the sidebar: required layout elements are missing.");
    return;
  }

  const isOpen = sidebar.classList.toggle("toggle-active");
  main.classList.toggle("toggle-active", isOpen);
  navbar.classList.toggle("toggle-active", isOpen);
  if (manageWrap) {
    manageWrap.classList.toggle("toggle-active", isOpen);
  }

  document.querySelectorAll("#top-navbar .toggle-btn, #side-nav .close-btn").forEach((button) => {
    button.setAttribute("aria-expanded", String(isOpen));
  });
}

// #################################
// popup

var c = 0;
function pop() {
  if (c == 0) {
    document.getElementById("popup-box").style.display = "block";
    c = 1;
  } else {
    document.getElementById("popup-box").style.display = "none";
    c = 0;
  }
}

// const popupMessagesButtons = document.querySelectorAll('popup-btn-messages')

// popupMessagesButtons.forEach(button, () => {
//     button.addEventListener('click', () => {
//         document.getElementById('popup-box-messages').style.display = 'none';
//     })
// })

// const popupMessagesButtom = document.getElementById('popup-btn-messages')
// popupMessagesButtom.addEventListener('click', () => {
//     document.getElementById('popup-box-messages').style.display = 'none';
// })
// ##################################

// Example starter JavaScript for disabling form submissions if there are invalid fields
// Fetch all the forms we want to apply custom Bootstrap validation styles to
var forms = document.getElementsByClassName("needs-validation");

// Loop over them and prevent submission
Array.prototype.filter.call(forms, function (form) {
  form.addEventListener(
    "submit",
    function (event) {
      if (form.checkValidity() === false) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add("was-validated");
    },
    false
  );
});
// ##################################

// extend and collapse
function showCourses(btn) {
  var btn = $(btn);

  if (collapsed) {
    btn.html('Collapse <i class="fas fa-angle-up"></i>');
    $(".hide").css("max-height", "unset");
    $(".white-shadow").css({ background: "unset", "z-index": "0" });
  } else {
    btn.html('Expand <i class="fas fa-angle-down"></i>');
    $(".hide").css("max-height", "150");
    $(".white-shadow").css({
      background: "linear-gradient(transparent 50%, rgba(255,255,255,.8) 80%)",
      "z-index": "2",
    });
  }
  collapsed = !collapsed;
}

$(document).ready(function () {
  $("#primary-search").focus(function () {
    $("#top-navbar").attr("class", "dim");
    $("#side-nav").css("pointer-events", "none");
    $("#main-content").css("pointer-events", "none");
  });
  $("#primary-search").focusout(function () {
    $("#top-navbar").removeAttr("class");
    $("#side-nav").css("pointer-events", "auto");
    $("#main-content").css("pointer-events", "auto");
  });

  if (typeof bootstrap !== 'undefined') {
    document.querySelectorAll('[data-bs-toggle="dropdown"]').forEach((dropdownToggle) => {
      bootstrap.Dropdown.getOrCreateInstance(dropdownToggle, {
        boundary: 'window',
        popperConfig: (defaultBsPopperConfig) => {
          const modifiers = defaultBsPopperConfig && defaultBsPopperConfig.modifiers
            ? [...defaultBsPopperConfig.modifiers]
            : [];
          modifiers.push(
            { name: 'preventOverflow', options: { boundary: 'window', altBoundary: true, tether: false } },
            { name: 'flip', options: { fallbackPlacements: ['top', 'bottom', 'right', 'left'] } }
          );
          return { ...defaultBsPopperConfig, modifiers };
        },
      });
    });
  }
});
