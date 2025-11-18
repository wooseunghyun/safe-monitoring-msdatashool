// 녹음 UI
export function setRecordingUI(isRecording) {
  const btn = document.getElementById("btn-record");
  const ind = document.getElementById("record-indicator");
  const timer = document.getElementById("record-timer");
  const text = document.getElementById("record-text");

  if (!btn) return;

  if (isRecording) {
    btn.classList.add("is-recording");
    btn.textContent = "⏹ 녹음 중지";
    ind.classList.add("active");
    text.textContent = "녹음 중...";
  } else {
    btn.classList.remove("is-recording");
    btn.textContent = "🎙 녹음 시작";
    ind.classList.remove("active");
    timer.textContent = "00:00";
    text.textContent = "대기 중";
  }
}

window.setRecordingUI = setRecordingUI;
