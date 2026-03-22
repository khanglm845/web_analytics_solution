CREATE DATABASE IF NOT EXISTS web_analytics_project
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci; 

USE web_analytics_project;


CREATE TABLE IF NOT EXISTS stocks (
    ticker VARCHAR(10) PRIMARY KEY,       
    company_name VARCHAR(255) NOT NULL,
    sector VARCHAR(100));


CREATE TABLE IF NOT EXISTS stock_prices (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    `time` DATETIME NOT NULL,   
    `open` DECIMAL(15, 2),         
    high DECIMAL(15, 2),
    low DECIMAL(15, 2),
	`close` DECIMAL(15, 2),
    volume BIGINT,
    ticker VARCHAR(10) NOT NULL,

    FOREIGN KEY (ticker) REFERENCES stocks(ticker) ON DELETE CASCADE,
    INDEX idx_ticker_time (ticker, `time`)
);


CREATE TABLE IF NOT EXISTS raw_news (
    news_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,      
    title VARCHAR(500) NOT NULL,         
    sapo TEXT,    
    content TEXT,         
	publish_time DATETIME NOT NULL, 
    url VARCHAR(750) UNIQUE,
    FOREIGN KEY (ticker) REFERENCES stocks(ticker) ON DELETE CASCADE,
    INDEX idx_news_time (ticker, publish_time)
);


CREATE TABLE IF NOT EXISTS news_analytics (
    analytics_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    news_id BIGINT NOT NULL UNIQUE, 
    ticker VARCHAR(10) NOT NULL,
    `text` TEXT,
    label VARCHAR(20),
    sentiment_score DECIMAL(5, 4) NOT NULL,             
    FOREIGN KEY (news_id) REFERENCES raw_news(news_id) ON DELETE CASCADE,
    FOREIGN KEY (ticker) REFERENCES stocks(ticker) ON DELETE CASCADE,
    INDEX idx_score (sentiment_score)
);