module.exports = {
    "port": "3001",
    "proxy": "localhost:8000",
    "files": ["assets/**/*.js", "assets/**/*.css", "assets/**/*.scss"],
    "watchOptions": {
        usePolling: true,
        interval: 1000,
        cwd: "/project"
    }
};
