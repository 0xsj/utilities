package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"strings"
)

func madin() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: go run script.go <input_file>")
		fmt.Println("Or pipe content: cat file.txt | go run script.go")
		return
	}

	var input []byte
	var err error

	if os.Args[1] != "-" {
		input, err = ioutil.ReadFile(os.Args[1])
		if err != nil {
			fmt.Printf("Error reading file: %v\n", err)
			return
		}
	} else {
		input, err = ioutil.ReadAll(os.Stdin)
		if err != nil {
			fmt.Printf("Error reading from stdin: %v\n", err)
			return
		}
	}

	inputStr := string(input)

	inputStr = strings.TrimSpace(inputStr)
	if strings.HasPrefix(inputStr, "\"") && strings.HasSuffix(inputStr, "\"") {
		inputStr = inputStr[1 : len(inputStr)-1]
	}

	var jsonData interface{}
	err = json.Unmarshal([]byte(inputStr), &jsonData)
	if err != nil {
		unescaped := strings.Replace(inputStr, "\\\"", "\"", -1)
		unescaped = strings.Replace(unescaped, "\\\\", "\\", -1)
		
		err = json.Unmarshal([]byte(unescaped), &jsonData)
		if err != nil {
			fmt.Printf("Error parsing JSON: %v\n", err)
			return	
		}
	}

	prettyJSON, err := json.MarshalIndent(jsonData, "", "  ")
	if err != nil {
		fmt.Printf("Error formatting JSON: %v\n", err)
		return
	}

	fmt.Println(string(prettyJSON))
}