let tabSwitchCount = 0;
let tabLimit = 3;
let formElement;

function setTabSwitchLimit(limit, formId) {
  tabSwitchCount = 0;
  tabLimit = limit;
  formElement = document.getElementById(formId);

  window.onblur = function () {
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

  // Optional: Warn user before leaving page
  window.onbeforeunload = function () {
    return "Are you sure you want to leave? Your exam will be submitted.";
  };
}
