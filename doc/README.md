# Documentation Index

Welcome to the OpenAQ Data Pipeline documentation. This index helps you find the right guide for your needs.

---

## 📚 Quick Navigation

### For New Users

**Start Here** → [Environment Setup Guide](ENVIRONMENT_SETUP.md)
- Complete installation instructions (Docker + local development)
- AWS account configuration
- Troubleshooting common setup issues
- **Time to complete**: 30-60 minutes

**Then Read** → [Main README](../README.md)
- Project overview and objectives
- Quick start guide
- Daily workflow examples
- Architecture summary

### For Developers

**System Architecture** → [Architecture Guide](architecture_en.md)
- High-level system design
- Data flow diagrams
- Zone-based storage (raw/dev/prod)
- Airflow orchestration patterns
- AWS infrastructure details
- Scalability considerations

**OpenAQ API Integration** → [API Integration Guide](API_INTEGRATION.md)
- Authentication and API keys
- Endpoints used (`/v3/locations`, `/v3/sensors/{id}/measurements`)
- Rate limiting strategies
- Error handling patterns
- Recent bug fixes (parameter filtering, city mapping)
- Example requests and responses

**Data Transformation** → [Glue Jobs Guide](GLUE_JOBS_GUIDE.md)
- PySpark transformation logic
- Input/output schemas
- 7-step transformation process
- Performance optimization
- CloudWatch monitoring
- Local testing strategies
- Troubleshooting common issues

**Code Standards** → [Refactoring Guide](REFACTORING_GUIDE.md)
- Shared logging utilities (`log_info`, `log_ok`, `log_fail`)
- Configuration constants (timeout values, API limits)
- Helper function patterns
- Error handling standards
- Migration guide for refactoring existing code
- Anti-patterns to avoid

**Comprehensive Reference** → [CLAUDE.md](../CLAUDE.md)
- Detailed implementation notes
- Common pitfalls and solutions
- Code navigation guide
- Historical context and decisions

---

## 🎯 Documentation by Task

### "I want to set up my development environment"
→ **[Environment Setup Guide](ENVIRONMENT_SETUP.md)**
- Docker installation and configuration
- AWS account creation
- Python virtual environment setup
- Verification steps

### "I want to understand the system architecture"
→ **[Architecture Guide](architecture_en.md)**
- Four-zone S3 structure explanation
- Data flow from API to dashboards
- Airflow DAG orchestration
- Dev vs Prod strategy

### "I need to integrate with OpenAQ API"
→ **[API Integration Guide](API_INTEGRATION.md)**
- API authentication
- Location and measurement endpoints
- Pagination and rate limiting
- Data extraction patterns

### "I need to modify Glue transformation logic"
→ **[Glue Jobs Guide](GLUE_JOBS_GUIDE.md)**
- Transformation step-by-step breakdown
- Schema definitions (input/output)
- Testing transformations locally
- Debugging PySpark jobs

### "I want to write clean, maintainable code"
→ **[Refactoring Guide](REFACTORING_GUIDE.md)**
- Logging utilities usage
- Named constants for magic numbers
- Helper function extraction
- Code organization principles

### "I'm encountering an error"
→ Check troubleshooting sections in:
1. **[Environment Setup Guide](ENVIRONMENT_SETUP.md)** - Setup and configuration errors
2. **[Glue Jobs Guide](GLUE_JOBS_GUIDE.md)** - Transformation and PySpark errors
3. **[CLAUDE.md](../CLAUDE.md)** - Common pitfalls section

---

## 📖 Documentation Structure

```
doc/
├── README.md                       # This file (documentation index)
├── ENVIRONMENT_SETUP.md            # Setup instructions
├── architecture_en.md              # System architecture (English)
├── architecture.md                 # System architecture (Vietnamese - legacy)
├── API_INTEGRATION.md              # OpenAQ API integration
├── GLUE_JOBS_GUIDE.md              # Glue transformation guide
├── REFACTORING_GUIDE.md            # Code standards and patterns
├── historical_backfill_2025_plan.md # Historical data backfill plan
├── AQI Calculation Implementation Plan.md # AQI feature planning
└── archive/                        # Historical documents
    ├── groovy-foraging-harbor.md
    ├── LAMBDA_BUG_FIX_REPORT.md
    └── plan.md
```

---

## 🚀 Recommended Learning Path

### Week 1: Foundation
1. ✅ Complete [Environment Setup Guide](ENVIRONMENT_SETUP.md)
2. ✅ Read [Main README](../README.md)
3. ✅ Run first DAG manually in Airflow UI
4. ✅ Explore S3 buckets to understand zone structure

### Week 2: Deep Dive
1. ✅ Study [Architecture Guide](architecture_en.md)
2. ✅ Read [API Integration Guide](API_INTEGRATION.md)
3. ✅ Run API extraction script: `python etls/openaq_etl.py`
4. ✅ Query Athena tables to verify data flow

### Week 3: Advanced Topics
1. ✅ Read [Glue Jobs Guide](GLUE_JOBS_GUIDE.md)
2. ✅ Review [Refactoring Guide](REFACTORING_GUIDE.md)
3. ✅ Test transformations locally with sample data
4. ✅ Make small code changes and observe results

### Week 4: Mastery
1. ✅ Study [CLAUDE.md](../CLAUDE.md) for comprehensive reference
2. ✅ Implement a new feature or fix a bug
3. ✅ Write tests for your changes
4. ✅ Deploy to dev environment and validate

---

## 📝 Document Maintenance

### Last Major Update: January 4, 2026

**Recent Changes**:
- ✅ Created comprehensive [Glue Jobs Guide](GLUE_JOBS_GUIDE.md)
- ✅ Created comprehensive [Refactoring Guide](REFACTORING_GUIDE.md)
- ✅ Created comprehensive [API Integration Guide](API_INTEGRATION.md)
- ✅ Created comprehensive [Environment Setup Guide](ENVIRONMENT_SETUP.md)
- ✅ Translated architecture.md to English ([architecture_en.md](architecture_en.md))

**Documentation Coverage**:

| Component | Coverage | Primary Document |
|-----------|----------|------------------|
| Environment Setup | ✅ Comprehensive | [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) |
| System Architecture | ✅ Comprehensive | [architecture_en.md](architecture_en.md) |
| API Integration | ✅ Comprehensive | [API_INTEGRATION.md](API_INTEGRATION.md) |
| Glue Transformations | ✅ Comprehensive | [GLUE_JOBS_GUIDE.md](GLUE_JOBS_GUIDE.md) |
| Code Standards | ✅ Comprehensive | [REFACTORING_GUIDE.md](REFACTORING_GUIDE.md) |
| Testing Patterns | 🔶 Partial | [tests/README.md](../tests/README.md) |
| Deployment Procedures | 🔶 Partial | [CLAUDE.md](../CLAUDE.md) |

**Legend**: ✅ Comprehensive | 🔶 Partial | ❌ Missing

### Contributing to Documentation

When updating documentation:

1. **Keep consistency** - Follow existing formatting and structure
2. **Update related docs** - If you change architecture, update all affected guides
3. **Version carefully** - Add "Last Updated" date at bottom of each document
4. **Link liberally** - Cross-reference related sections with markdown links
5. **Test examples** - Ensure all code examples actually run
6. **Update this index** - Add new documents to navigation sections

**Style Guide**:
- Use markdown headers (`#`, `##`, `###`) for hierarchy
- Use tables for structured comparisons
- Use code blocks with language hints (```python, ```bash)
- Use emojis sparingly in headings for visual navigation (📚, 🚀, ⚠️)
- Use **bold** for emphasis, `code` for technical terms
- Use blockquotes for important notes (> ⚠️ Warning: ...)

---

## 🔗 External Resources

### OpenAQ
- [OpenAQ Website](https://openaq.org/)
- [API Documentation](https://api.openaq.org/docs)
- [Community Forum](https://github.com/openaq/openaq-api/discussions)

### AWS Documentation
- [AWS Glue Developer Guide](https://docs.aws.amazon.com/glue/)
- [Amazon Athena User Guide](https://docs.aws.amazon.com/athena/)
- [Amazon S3 User Guide](https://docs.aws.amazon.com/s3/)
- [AWS Lambda Developer Guide](https://docs.aws.amazon.com/lambda/)

### Apache Airflow
- [Airflow Documentation](https://airflow.apache.org/docs/apache-airflow/2.7.1/)
- [DAG Authoring Best Practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html)
- [Operators and Hooks](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/operators/index.html)

### PySpark
- [PySpark 3.4.1 Documentation](https://spark.apache.org/docs/3.4.1/api/python/)
- [Spark SQL Guide](https://spark.apache.org/docs/3.4.1/sql-programming-guide.html)
- [Parquet File Format](https://parquet.apache.org/docs/)

---

## 💡 Tips for Documentation Users

### Finding Information Quickly

**Use Browser Search (Ctrl+F / Cmd+F)**:
- Search for error messages in troubleshooting sections
- Search for function names to find usage examples
- Search for "Example" to find code samples

**Use GitHub's Search**:
- Search across all documentation files
- Search for specific code patterns
- Search commit history for context

**Check Multiple Sources**:
- Quick answer needed → [README](../README.md)
- Deep understanding → [Architecture Guide](architecture_en.md)
- Implementation details → [CLAUDE.md](../CLAUDE.md)
- Specific error → Troubleshooting sections

### Effective Documentation Reading

1. **Start with overview** - Don't dive into details immediately
2. **Follow links** - Cross-references provide important context
3. **Try examples** - Run code snippets to verify understanding
4. **Take notes** - Document your own learnings and gotchas
5. **Ask questions** - If documentation is unclear, request clarification

---

## 📧 Feedback and Support

**Documentation Issues**:
- Found outdated information? Create a GitHub issue
- Have suggestions? Submit a pull request
- Unclear explanation? Ask in team chat

**Technical Support**:
- Setup issues → Check [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) troubleshooting
- Runtime errors → Check [Glue Jobs Guide](GLUE_JOBS_GUIDE.md) troubleshooting
- Architecture questions → Review [architecture_en.md](architecture_en.md)
- Still stuck? Contact the OpenAQ Pipeline Team

---

**Maintained By**: OpenAQ Pipeline Team  
**Last Updated**: January 4, 2026  
**Next Review**: February 2026
