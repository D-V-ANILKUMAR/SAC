function startTimer(durationMinutes, formId) {
  let form = document.getElementById(formId);
  // Store the start time in sessionStorage to survive reloads
  let startTime = sessionStorage.getItem("exam_start");
  if (!startTime) {
    startTime = Date.now();
    sessionStorage.setItem("exam_start", startTime);
  } else {
    startTime = parseInt(startTime);
  }

  let duration = durationMinutes * 60; // total seconds

  let timerInterval = setInterval(function () {
    let now = Date.now();
    let elapsed = Math.floor((now - startTime) / 1000); // seconds
    let remaining = duration - elapsed;

    if (remaining <= 0) {
      clearInterval(timerInterval);
      sessionStorage.removeItem("exam_start");
      alert("Time is up! Submitting exam.");
      form.submit();
    }

    let mins = Math.floor(remaining / 60);
    let secs = remaining % 60;
    document.title = mins + ":" + (secs < 10 ? "0" : "") + secs;
  }, 1000);
}
