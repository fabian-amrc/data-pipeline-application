FROM bitnamilegacy/spark:3.5.3

ENV JAVA_HOME=/opt/bitnami/java
ENV PATH="${JAVA_HOME}/bin:${PATH}"

USER root

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates dos2unix python3-pip \
  && rm -rf /var/lib/apt/lists/*

COPY certs/ /tmp/spark-certs/

RUN if [ -f /tmp/spark-certs/minikubeCA.crt ]; then \
    dos2unix /tmp/spark-certs/minikubeCA.crt; \
    keytool -importcert -noprompt \
      -alias minio-ca \
      -file /tmp/spark-certs/minikubeCA.crt \
      -keystore "${JAVA_HOME}/lib/security/cacerts" \
      -storepass changeit; \
  fi \
  && rm -rf /tmp/spark-certs

WORKDIR /app

RUN pip install --no-cache-dir pyspark==3.5.3

# Delta Lake jars
ADD https://repo1.maven.org/maven2/io/delta/delta-spark_2.12/3.3.0/delta-spark_2.12-3.3.0.jar /opt/bitnami/spark/jars/
ADD https://repo1.maven.org/maven2/io/delta/delta-standalone_2.12/3.3.0/delta-standalone_2.12-3.3.0.jar /opt/bitnami/spark/jars/
ADD https://repo1.maven.org/maven2/io/delta/delta-storage/3.3.0/delta-storage-3.3.0.jar /opt/bitnami/spark/jars/

# S3A / MinIO jars
ADD https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar /opt/bitnami/spark/jars/
ADD https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar /opt/bitnami/spark/jars/

# Unity Catalog jars
ADD https://repo1.maven.org/maven2/io/unitycatalog/unitycatalog-spark_2.12/0.2.1/unitycatalog-spark_2.12-0.2.1.jar /opt/bitnami/spark/jars/
ADD https://repo1.maven.org/maven2/io/unitycatalog/unitycatalog-client/0.2.1/unitycatalog-client-0.2.1.jar /opt/bitnami/spark/jars/
ADD https://repo1.maven.org/maven2/org/openapitools/jackson-databind-nullable/0.2.6/jackson-databind-nullable-0.2.6.jar /opt/bitnami/spark/jars/
ADD https://repo1.maven.org/maven2/com/google/code/findbugs/jsr305/3.0.2/jsr305-3.0.2.jar /opt/bitnami/spark/jars/

# Kafka jars
ADD https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.3/spark-sql-kafka-0-10_2.12-3.5.3.jar /opt/bitnami/spark/jars/
ADD https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/2.8.2/kafka-clients-2.8.2.jar /opt/bitnami/spark/jars/
ADD https://repo1.maven.org/maven2/org/apache/spark/spark-streaming-kafka-0-10-assembly_2.12/3.5.3/spark-streaming-kafka-0-10-assembly_2.12-3.5.3.jar /opt/bitnami/spark/jars/
ADD https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.3/spark-token-provider-kafka-0-10_2.12-3.5.3.jar /opt/bitnami/spark/jars/

# Apache jars
ADD https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.12.1/commons-pool2-2.12.1.jar /opt/bitnami/spark/jars/

COPY conf/spark-defaults.conf /opt/bitnami/spark/conf.default/spark-defaults.conf
COPY scripts/entrypoint.sh /opt/data-pipeline/entrypoint.sh

RUN chmod -R a+r /opt/bitnami/spark/jars /opt/bitnami/spark/conf.default/spark-defaults.conf \
  && chmod +x /opt/data-pipeline/entrypoint.sh

WORKDIR /app

RUN if ! getent group 1001 >/dev/null; then \
    echo "spark:x:1001:" >> /etc/group; \
  fi \
  && if ! getent passwd 1001 >/dev/null; then \
    echo "spark:x:1001:1001:Spark User:/app:/sbin/nologin" >> /etc/passwd; \
  fi \
  && chown -R 1001:1001 /app /opt/bitnami/spark

ENV USER=spark
ENV LOGNAME=spark
ENV SPARK_USER=spark
ENV HADOOP_USER_NAME=spark

ENTRYPOINT ["/opt/data-pipeline/entrypoint.sh"]

USER 1001
