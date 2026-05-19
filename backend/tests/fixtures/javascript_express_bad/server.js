const express = require("express");
const axios = require("axios");

const app = express();
const cache = new Map();

app.get("/users", async (req, res) => {
  const users = await axios.get("https://api.example.com/users");
  for (const u of users.data) {
    const detail = await axios.get(`https://api.example.com/users/${u.id}`);
    cache.set(u.id, detail.data);
  }
  res.json(Array.from(cache.values()));
});

app.listen(3000);
