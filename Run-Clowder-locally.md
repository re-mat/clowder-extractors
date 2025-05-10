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
#### 2.1 Set up Box Token as enviormnet variable
Parameter extractor expects a Box token to be set as an environment variable. Get the box token(client secret) from https://uofi.app.box.com/developers/console/app/2374837/configuration
You will need sufficient permission to access the portal. Contact[ bengal1@illinois.edu]() for access/token.
You can set it up by running the following command in terminal or add in your bash/zhrc file:
```sh
export BOX_TOKEN={service_account_box_token}
```
This environment variable needs to be set up in local system before running the docker-compose command.

#### 2.2 Set up Docker
To start Clowder, ensure that the `docker-compose.yml` and `docker-compose-remat-extractors.yml` files are present:

```sh
   docker-compose -f docker-compose.yml -f docker-compose-remat-extractors.yml up -d
```

#### Common Issues:
- **If you encounter an `Unpigz` error on an Apple Silicon chip**
This is caused by the docker client assuming the `unpigz` binary is present in `/usr/bin/unpigz`, which is not brew
installs the correct binary Apple Silicon Macs. The `unpigz` binary is a part of the `pigz` package.
  1. Install `pigz` using Homebrew:
     ```sh
     brew install pigz
     ```
  2. Set the `DOCKER_UNPIGZ_BINARY` environment variable:
     ```sh
     export DOCKER_UNPIGZ_BINARY=$(which pigz)
     ```
  3. Restart the docker compose stack.

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
