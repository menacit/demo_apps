// > favorites - Mark cocktail recipes as favorites.
//
// Example usage:
//
// GET /api/favorites/bob : Get favorites for Bob.
// "Screwdriver" | POST /api/favorites/ada : Add drink as favorite for Ada.
// GET / : Health/Readiness end-point.
//
// Listens for HTTP on port 8000/TCP by default.
// Settings configurable using environment variables:
//
// "APP_ACCESS_KEY":
// Simple key/token used for authenticating client requests.
//
// "APP_DATABASE_URL":
// HTTP or HTTPS connection URL to rqlite database.
//
// "APP_DATABASE_USER":
// Username for database connection.
//
// "APP_DATABASE_PASSWORD":
// Password for database connection.

package main

import (
	"os"
	"log"
	"fmt"
	"strings"
	"net/http"
	"net/url"
	"io/ioutil"
	"encoding/json"
	"github.com/rqlite/gorqlite"
)

var accessKey, databaseURL, databaseUser, databasePassword, hostString string
var databaseConnection *gorqlite.Connection

// ---
func init() {
	hostName, err := os.Hostname()
	if err != nil {
		log.Fatal("Failed to get hostname for running system")
	}

	kubernetesNodeName := os.Getenv("K8S_NODE_NAME")
	if kubernetesNodeName != "" {
		hostString = fmt.Sprintf("pod %s on node %s", hostName, kubernetesNodeName)

	} else {
		hostString = "host " + hostName
	}
	
	accessKey = os.Getenv("APP_ACCESS_KEY")
	databaseURL = os.Getenv("APP_DATABASE_URL")
	databaseUser = os.Getenv("APP_DATABASE_USER")
	databasePassword = os.Getenv("APP_DATABASE_PASSWORD")

	if accessKey == "" || databaseURL == "" {
		log.Fatal("Environment variable APP_ACCESS_KEY or APP_DATABASE_URL missing")
	}

	if databaseUser != "" && databasePassword != "" {
		log.Print("Reading username/password from dedicated environment variables")
		
		parsedDatabaseURL, err := url.Parse(databaseURL)
		if err != nil {
			log.Fatal("Failed to parse database connection URL: ", databaseURL)
		}

		parsedDatabaseURL.User = url.UserPassword(databaseUser, databasePassword)
		databaseURL = parsedDatabaseURL.String()
	}

	log.Print("Opening connection to rqlite database")
	databaseConnection, err = gorqlite.Open(databaseURL)
	if err != nil {
		log.Fatal("Failed to open database connection: ", err)
	}

	err = databaseConnection.SetConsistencyLevel(gorqlite.ConsistencyLevelStrong)
	if err != nil {
		log.Fatal("Failed to configure database consistency level: ", err)
	}

	writeResult, err := databaseConnection.WriteOne(`
		CREATE TABLE IF NOT EXISTS "favorites"
		("id" INTEGER, "timestamp" DATETIME DEFAULT CURRENT_TIMESTAMP,
		"user" TEXT, "drink" TEXT, PRIMARY KEY ("id" AUTOINCREMENT))`)

	if err != nil || writeResult.Err != nil {
		log.Fatalf(
			"Failed to create database table for favorites: \"%s\", \"%s\"",
			err, writeResult.Err)
	}

	return
}

// ---
func healthHandler(response http.ResponseWriter, request *http.Request) {
	response.Header().Add("X-Provided-By", hostString)
	
	if request.Method != "GET" {
		http.Error(response, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	queryRows, err := databaseConnection.QueryOne("SELECT id FROM favorites")
	if err != nil || queryRows.Err != nil {
		log.Printf(
			"Failed query database during health-check: \"%s\", \"%s\"",
			err, queryRows.Err)

		http.Error(response, "Database unavailable", http.StatusInternalServerError)
		return
	}

	response.Write(
		[]byte(fmt.Sprintf("Hello from favorites API server on %s!\n", hostString)))

	return
}

// ---
func favoritesHandler(response http.ResponseWriter, request *http.Request) {
	response.Header().Add("X-Provided-By", hostString)
	
	if request.Method != "GET" && request.Method != "POST" {
		http.Error(response, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if request.Header.Get("X-Access-Key") != accessKey {
		log.Print("Received favorites request with incorrect access key")
		http.Error(response, "Invalid access key", http.StatusUnauthorized)
		return
	}

	user := strings.TrimPrefix(request.URL.Path, "/api/favorites/")
	if user == "" {
		log.Print("Received favorites request without target user specified")
		http.Error(response, "URL path missing username", http.StatusBadRequest)
		return
	}

	if request.Method == "GET" {
		log.Printf("Returning list of favorites for user \"%s\"", user)

		queryRows, err := databaseConnection.QueryOneParameterized(
			gorqlite.ParameterizedStatement{
				Query: "SELECT DISTINCT drink FROM favorites WHERE user = ?",
				Arguments: []interface{}{user},},)

		if err != nil || queryRows.Err != nil {
			log.Printf(
				"Failed query database for user \"%s\" favorites: \"%s\", \"%s\"",
				user, err, queryRows.Err)

			http.Error(
				response, "Failed to query database", http.StatusInternalServerError)

        	return
		}
		
		favorites := []string{}
		for queryRows.Next() {
			var favorite string

			if err := queryRows.Scan(&favorite); err != nil {
				log.Print("Failed to query database for favorites: ", err)
				http.Error(
					response, "Failed to query database", http.StatusInternalServerError)

        		return
        	}
		
        	favorites = append(favorites, favorite)
		}

		response.Header().Set("Content-Type", "application/json")
		responseData, _ := json.Marshal(favorites)
		response.Write(responseData)
		return
	}
	
	log.Printf("Handling request to add favorite for user \"%s\"", user)
	
	defer request.Body.Close()
	requestBody, err := ioutil.ReadAll(request.Body)
	if err != nil {
		log.Print("Failed to read body for favorite addition request: ", err)
		http.Error(response, "Failed to read submitted body", http.StatusBadRequest)
		return
	}

	var drink string
	if err := json.Unmarshal(requestBody, &drink); err != nil {
		log.Print("Failed to parse body for favorite addition request: ", err)
		http.Error(response, "Failed to parse submitted body", http.StatusBadRequest)
		return
	}

	log.Printf("Adding drink \"%s\" as favorite for user \"%s\"", drink, user)
	
	writeResult, err := databaseConnection.WriteOneParameterized(
		gorqlite.ParameterizedStatement{
			Query: "INSERT INTO favorites (user, drink) VALUES (?, ?)",
			Arguments: []interface{}{user, drink},},)

	if err != nil || writeResult.Err != nil {
		log.Printf(
			"Failed to persist \"%s\" as favorite for user \"%s\": \"%s\", \"%s\"",
			drink, user, err, writeResult.Err)

		http.Error(
			response, "Failed to write to database", http.StatusInternalServerError)

       	return
	}

	return
}

// ---
func main() {
	http.HandleFunc("/", healthHandler)
	http.HandleFunc("/api/favorites/", favoritesHandler)

	log.Print("Starting favorites web server on ", hostString)
	log.Fatal(http.ListenAndServe(":8000", nil))
}
