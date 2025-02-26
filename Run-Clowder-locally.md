# Installation Guide for Clowder and Remat Extractors

## Run Clowder Locally

### 1. Apple Silicon Mac - M Series Considerations
If you are using an Apple Silicon Mac (M series), you will need to either:
- Turn off Elasticsearch from `docker-compose.yml`
- (or) Follow the steps below to run Qemu:

### 1.2 Else Skip to Step 2

#### Steps:
1. **Pull Qemu:**
   ```sh
   docker pull --platform=linux/arm64 multiarch/qemu-user-static
   ```
2. **Run Qemu:**
   ```sh
   docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
   ```
3. Add the following to the `docker-compose.yml` under the `elasticsearch` image if not already present:
   ```yaml
    platform: linux/amd64
   ```

### 2. Run Clowder
To start Clowder, ensure that the `docker-compose.yml` and `docker-compose-remat-extractors.yml` files are present:

```sh
   docker-compose -f docker-compose.yml -f docker-compose-remat-extractors.yml up -d
```

#### Common Issues:
- **If you encounter an `Unpigz` error on an Apple Silicon chip:**
  1. **Fix the error:**
     ```sh
     sudo rm /usr/bin/unpigz
     brew install pigz
     sudo ln -s $(which pigz) /usr/bin/unpigz
     ```
  2. **Verify the installation:**
     ```sh
     unpigz --version
     ```

- **Clowder should now be running at:**
  - `http://localhost:8000`

### 3. Create a New Account and Login to Clowder

To create a new user account, follow these steps:

1. Run the following command:
   ```sh
   docker run -ti --rm --platform=linux/amd64 --network clowder-extractors_clowder clowder/mongo-init
   ```
2. Ensure the `--network` parameter is `{repo_name}_clowder`.
3. When prompted, enter the following details:
   ```plaintext
   EMAIL_ADDRESS : email@illinois.edu
   FIRST_NAME    : {name}
   LAST_NAME     : {name}
   PASSWORD      : {password}
   ADMIN         : true
   Inserted user (id=67b83c8a64dcc287f06be5f0)
   Updated user count (0 match, 0 updated)
   Inserted new user with id = email@illinois.edu
   ```
4. Login to Clowder at `http://localhost:8000` using the above credentials.

### 4. Verify Registered Extractors
To check the list of registered extractors, visit:
- `http://localhost:8000/monitor/`
