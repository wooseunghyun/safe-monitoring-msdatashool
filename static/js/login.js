// Firebase SDK import
import { initializeApp } from "https://www.gstatic.com/firebasejs/12.6.0/firebase-app.js";
import {
  getAuth,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  updateProfile
} from "https://www.gstatic.com/firebasejs/12.6.0/firebase-auth.js";

// Firebase config
const firebaseConfig = {
  apiKey: "AIzaSyBR6lk0zzyo1fuSIIUh0iMKWY2w01yUta0",
  authDomain: "powerquatrogirls.firebaseapp.com",
  projectId: "powerquatrogirls",
  storageBucket: "powerquatrogirls.firebasestorage.app",
  messagingSenderId: "217906578696",
  appId: "1:217906578696:web:dc64e05945218aefe398bd",
  measurementId: "G-39BV92L1ET"
};

// Firebase 초기화
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// HTML 요소 가져오기
const guardianName = document.getElementById("guardian-name");
const guardianContact = document.getElementById("guardian-contact");

const userName = document.getElementById("user-name");
const signupEmail = document.getElementById("signup-email");
const signupPassword = document.getElementById("signup-password");
const signupBtn = document.getElementById("signup-btn");

const loginEmail = document.getElementById("login-email");
const loginPassword = document.getElementById("login-password");
const loginBtn = document.getElementById("login-btn");

const logoutBtn = document.getElementById("logout-btn");

const message = document.getElementById("message");

// 회원가입 기능
signupBtn.addEventListener("click", async () => {
  try {
    // 1) Firebase Auth 생성
    const userCredential = await createUserWithEmailAndPassword(
      auth,
      signupEmail.value,
      signupPassword.value
    );

    // 2) 추가 정보 저장 (displayName, photoURL 활용)
    await updateProfile(auth.currentUser, {
      displayName: userName.value,
      photoURL: JSON.stringify({
        guardian_name: guardianName.value,
        guardian_contact: guardianContact.value
      })
    });

    message.textContent = `회원가입 성공: ${userCredential.user.email}`;

  } catch (error) {
    message.textContent = `회원가입 오류: ${error.message}`;
  }
});

// 로그인 기능
loginBtn.addEventListener("click", async () => {
  try {
    const userCredential = await signInWithEmailAndPassword(
      auth,
      loginEmail.value,
      loginPassword.value
    );

    const user = userCredential.user;

    let guardianInfo = "";
    if (user.photoURL) {
      const info = JSON.parse(user.photoURL);
      guardianInfo = `보호자: ${info.guardian_name}, 연락처: ${info.guardian_contact}`;
    }

    message.textContent = `로그인 성공: ${user.email} / 사용자 이름: ${user.displayName} / ${guardianInfo}`;

  } catch (error) {
    message.textContent = `로그인 오류: ${error.message}`;
  }
});

// 로그아웃 기능
logoutBtn.addEventListener("click", async () => {
  try {
    await signOut(auth);
    message.textContent = "로그아웃 성공!";
  } catch (error) {
    message.textContent = `로그아웃 오류: ${error.message}`;
  }
});
