// Tilbot's login to its database, made once, when MongoDB starts on an empty volume.
// The same as db/init.js in Tilbot's repository; compose.yaml passes the name and password.
db.getSiblingDB("admin").createUser({
  user: process.env.MONGO_TILBOT_USER,
  pwd: process.env.MONGO_TILBOT_PASSWORD,
  roles: [{ role: "readWrite", db: "tilbot" }],
});
