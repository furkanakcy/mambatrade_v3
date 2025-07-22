import streamlit as st
from database import check_user

def login_form():
    """Streamlit için bir giriş formu oluşturur ve kimlik doğrulamayı yönetir."""
    
    # Oturum durumunu başlat
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    # Eğer kullanıcı zaten giriş yapmışsa, formu gösterme
    if st.session_state['logged_in']:
        return True

    st.title("Binance AI Trade Bot'a Hoş Geldiniz")
    st.subheader("Lütfen Giriş Yapın")

    with st.form("login_form"):
        username = st.text_input("Kullanıcı Adı", key="login_username")
        password = st.text_input("Parola", type="password", key="login_password")
        submitted = st.form_submit_button("Giriş Yap")

        if submitted:
            if check_user(username, password):
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.success("Başarıyla giriş yapıldı!")
                # Sayfanın yeniden yüklenmesini tetikleyerek ana uygulamayı göster
                st.rerun()
            else:
                st.error("Kullanıcı adı veya parola hatalı!")
    
    return False
