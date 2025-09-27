function startTimer(durationMinutes, formId, examId) {
  let form = document.getElementById(formId);
  // Build a unique key per exam so each take starts fresh
  const key = `exam_start_${examId}`;
  // Store the start time in sessionStorage to survive reloads
  let startTime = sessionStorage.getItem(key);
  if (!startTime) {
    startTime = Date.now();
    sessionStorage.setItem(key, startTime);
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
      sessionStorage.removeItem(key);
      alert("Time is up! Submitting exam.");
      form.submit();
    }

    let mins = Math.floor(remaining / 60);
    let secs = remaining % 60;
    document.title = mins + ":" + (secs < 10 ? "0" : "") + secs;
  }, 1000);
}

function resetTimer(examId) {
  const key = `exam_start_${examId}`;
  sessionStorage.removeItem(key);
}
