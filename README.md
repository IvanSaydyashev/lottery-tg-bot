# lottery-tg-bot

**This telegram bot will help you create awesome lotteries 🎉!**

## Video tutorial (in russian)

https://github.com/user-attachments/assets/29dfa274-dea6-4add-9044-6248a234ccee

## Run bot on your server

Before cloning repository you should visit [console firebase site](https://console.firebase.google.com/) and setup there your project

### Setup Firebase Realtime
Steps:
1. Create Firebase Project
2. Enter your project name
3. Select *Build* section and choose *Realtime Database*
4. Tap *Create Database*
5. Choose location and *Start in locked mode*

Nice!

### Setup project

#### Clone the repository
```bash
git clone git@github.com:IvanSaydyashev/lottery-tg-bot.git
cd lottery-tg-bot
```
#### Create .env file
```bash
touch .env
```
Here you need to store some private keys
- TOKEN - Your telegram bot token
- FIREBASE_SECRET - Location of your Firebase secrets
- FIREBASE_URL - Firebase url
- BOT_USERNAME - Bot's username

##### Getting Firebase secrets
Url you can find on the page of your base (Build -> Realtime Database)
File with secrets you can find in (Project settings -> Service accounts -> Generate new private key)

### Run your bot!
```bash
uv run main.py # uv - Unified Python packaging (you can use poetry or pip if you want but don't forget to download dependancies)
```
