let tabSwitchCount = 0;
let tabLimit = 3;
let formElement;
let isSubmitting = false;

function setTabSwitchLimit(limit, formId) {
  tabSwitchCount = 0;
  tabLimit = limit;
  formElement = document.getElementById(formId);

  // Disable tab tracking after submit
  function disableTabTracking() {
    window.onblur = null;
    window.onbeforeunload = null;
  }

  // Mark when exam is being submitted
  formElement.addEventListener("submit", function () {
    isSubmitting = true;
    disableTabTracking(); // ✅ Stop tab tracking immediately
  });

  // Detect tab switch
  window.onblur = function () {
    if (isSubmitting) return; // Ignore if submitting

    tabSwitchCount++;
    if (tabSwitchCount >= tabLimit) {
      alert("You have switched tabs too many times! Submitting exam.");
      formElement.submit();
    } else {
      alert(
        "Warning! You switched tab (" + tabSwitchCount + "/" + tabLimit + ")"
      );
    }
  };

  // Warn user only if not submitting
  window.onbeforeunload = function () {
    if (!isSubmitting) {
      return "Are you sure you want to leave? Your exam will be submitted.";
    }
  };
}
