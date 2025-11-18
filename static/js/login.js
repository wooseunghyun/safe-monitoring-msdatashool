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

// HTML 요소
const loginView = document.getElementById("login-view");
const signupView = document.getElementById("signup-view");

const loginEmail = document.getElementById("login-email");
const loginPassword = document.getElementById("login-password");
const loginBtn = document.getElementById("login-btn");

const signupBtn = document.getElementById("signup-btn");
const goSignupBtn = document.getElementById("go-signup-btn");
const goLoginBtn = document.getElementById("go-login-btn");

const signupEmail = document.getElementById("signup-email");
const signupPassword = document.getElementById("signup-password");
const userName = document.getElementById("user-name");
const guardianName = document.getElementById("guardian-name");
const guardianContact = document.getElementById("guardian-contact");

const message = document.getElementById("message");


// 🔥 화면 전환 기능
goSignupBtn.addEventListener("click", () => {
  loginView.style.display = "none";
  signupView.style.display = "block";
  message.textContent = "";
});

goLoginBtn.addEventListener("click", () => {
  signupView.style.display = "none";
  loginView.style.display = "block";
  message.textContent = "";
});


// 🔥 회원가입 기능
signupBtn.addEventListener("click", async () => {
  try {
    const userCredential = await createUserWithEmailAndPassword(
      auth,
      signupEmail.value,
      signupPassword.value
    );

    const extraInfo = {
      guardian_name: guardianName.value,
      guardian_contact: guardianContact.value,
      user_name: userName.value
    };

    await updateProfile(auth.currentUser, {
      displayName: userName.value,
      photoURL: JSON.stringify(extraInfo)
    });

    message.style.color = "green";
    message.textContent = "회원가입 완료! 이제 로그인해주세요.";

    // 회원가입 후 로그인 화면으로 자동 이동
    signupView.style.display = "none";
    loginView.style.display = "block";

  } catch (error) {
    message.style.color = "red";
    message.textContent = `회원가입 오류: ${error.message}`;
  }
});


// 🔥 로그인 기능
loginBtn.addEventListener("click", async () => {
  try {
    await signInWithEmailAndPassword(auth, loginEmail.value, loginPassword.value);

    message.style.color = "green";
    message.textContent = "로그인 성공!";

    // 로그인 성공 후 이동할 페이지
    // window.location.href = "/home";

  } catch (error) {
    message.style.color = "red";
    message.textContent = `로그인 오류: ${error.message}`;
  }
});
